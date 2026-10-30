"""Real PostgreSQL row-lock and idempotency tests; never run on SQLite."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from threading import Barrier, Event, Lock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from apps.accounts.models import Account
from apps.transactions.models import Transaction
from apps.transactions.services import TransactionService
from apps.users.models import User
from apps.users.routes import get_db
from apps.users.services import AuthenticationService
from core.db import Base
from main import app


@dataclass
class PostgresAPI:
    client: TestClient
    engine: Engine
    sessions: sessionmaker
    account_ids: list[int]
    headers: dict[str, str] = field(repr=False)


@pytest.fixture
def postgres_api():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip(
            "Set TEST_POSTGRES_URL to run PostgreSQL concurrency tests"
        )
    if make_url(url).get_backend_name() != "postgresql":
        pytest.fail("TEST_POSTGRES_URL must point to PostgreSQL")

    # Every test owns a fresh schema, not the database or existing app tables.
    schema = "concurrency_" + uuid4().hex
    admin = create_engine(url)
    engine = None
    previous_overrides = app.dependency_overrides.copy()
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = create_engine(
            url,
            connect_args={"options": (
                f"-csearch_path={schema} "
                "-clock_timeout=10000 -cstatement_timeout=15000"
            )},
        )
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as db:
            user = User(
                email="concurrent@example.com", hashed_password="unused",
                is_active=True, is_verified=True,
            )
            db.add(user)
            db.flush()
            accounts = [Account(
                user_id=user.id, name=f"Account {i}", currency="USD",
                balance=Decimal("100.00"), is_active=True,
            ) for i in range(2)]
            db.add_all(accounts)
            db.commit()
            account_ids = [account.id for account in accounts]
            token = AuthenticationService.create_tokens(user).access_token

        def override_get_db():
            # A separate connection/transaction for each HTTP request.
            with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as client:
            yield PostgresAPI(
                client=client, engine=engine, sessions=sessions,
                account_ids=account_ids,
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if engine is not None:
            engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(
                schema, cascade=True, if_exists=True,
            ))
        admin.dispose()


def post_parallel(api, monkeypatch, requests, *, same_account=True):
    """Force both initial key lookups to miss before either write starts."""
    initial_reads = Barrier(2, timeout=10)
    final_reads = Barrier(2, timeout=10)
    original_lookup = TransactionService.find_idempotent_transaction

    def lookup(db, *args):
        in_transaction = db.in_transaction()
        result = original_lookup(db, *args)
        calls = db.info.get("key_lookup_count", 0) + 1
        db.info["key_lookup_count"] = calls
        if calls == 1:
            assert result is None
            initial_reads.wait()
        elif calls == 2 and not same_account and in_transaction:
            # Both requests must reach the insert. The user-scoped database
            # constraint, not a lucky precheck, must resolve this conflict.
            assert result is None
            final_reads.wait()
        return result

    monkeypatch.setattr(
        TransactionService, "find_idempotent_transaction", lookup
    )
    original_lock = TransactionService.get_user_account
    lock_held = Event()
    release_lock = Event()
    guard = Lock()
    holder = []
    account_reads = Barrier(2, timeout=10)

    def lock_account(account_id, user_id, db):
        account = original_lock(account_id, user_id, db)
        if not same_account:
            # Distinct account locks do not serialize a user's shared key.
            account_reads.wait()
            return account
        with guard:
            first = not holder
            if first:
                holder.append(db.scalar(text("SELECT pg_backend_pid()")))
                lock_held.set()
        if first:
            assert release_lock.wait(10), "Coordinator did not release lock"
        return account

    monkeypatch.setattr(
        TransactionService, "get_user_account", lock_account
    )

    def post(request):
        account_id, amount, key = request
        return api.client.post(
            "/api/v1/transactions/",
            headers={**api.headers, "Idempotency-Key": key},
            json={
                "account_id": account_id, "type": "expense",
                "amount": amount, "currency": "USD",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post, request) for request in requests]
        try:
            if same_account:
                assert lock_held.wait(10), "No account lock acquired"
                # Verify real contention in PostgreSQL, not just two threads.
                deadline = time.monotonic() + 5
                with api.engine.connect() as connection:
                    while True:
                        blocked = connection.scalar(text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE :holder = ANY(pg_blocking_pids(pid)))"
                        ), {"holder": holder[0]})
                        if blocked:
                            break
                        assert time.monotonic() < deadline, (
                            "Second request did not wait for the account lock"
                        )
                        time.sleep(0.01)
        finally:
            release_lock.set()
        return [future.result(timeout=20) for future in futures]


@pytest.mark.parametrize(
    "amounts, expected_statuses, expected_balance, expected_count",
    [
        (["40.00", "30.00"], [201, 201], "30.00", 2),
        (["80.00", "80.00"], [201, 400], "20.00", 1),
    ],
)
def test_simultaneous_expenses_preserve_balance(
    postgres_api, monkeypatch, amounts, expected_statuses,
    expected_balance, expected_count,
):
    api = postgres_api
    account_id = api.account_ids[0]
    responses = post_parallel(api, monkeypatch, [
        (account_id, amount, f"expense-{i}")
        for i, amount in enumerate(amounts)
    ])
    assert sorted(r.status_code for r in responses) == expected_statuses
    for response in responses:
        if response.status_code == 400:
            assert response.json()["detail"] == "Insufficient account balance"
    with api.sessions() as db:
        account = db.get(Account, account_id)
        transactions = db.query(Transaction).all()
        assert account.balance == Decimal(expected_balance)
        assert len(transactions) == expected_count
        assert all(t.balance_after >= 0 for t in transactions)
        assert account.balance == Decimal("100") - sum(
            t.amount for t in transactions
        )


def test_simultaneous_same_key_replays_even_if_balance_is_now_insufficient(
    postgres_api, monkeypatch,
):
    api = postgres_api
    account_id = api.account_ids[0]
    responses = post_parallel(api, monkeypatch, [
        (account_id, "80.00", "same-key"),
        (account_id, "80.00", "same-key"),
    ])
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert responses[0].json() == responses[1].json()
    with api.sessions() as db:
        assert db.get(Account, account_id).balance == Decimal("20.00")
        assert db.query(Transaction).count() == 1


@pytest.mark.parametrize("same_account", [True, False])
def test_simultaneous_same_key_with_different_payload_is_conflict(
    postgres_api, monkeypatch, same_account,
):
    api = postgres_api
    first_id, second_id = api.account_ids
    responses = post_parallel(api, monkeypatch, [
        (first_id, "80.00", "same-key"),
        (first_id if same_account else second_id, "70.00", "same-key"),
    ], same_account=same_account)
    assert sorted(r.status_code for r in responses) == [201, 409]
    conflict = next(r for r in responses if r.status_code == 409)
    assert "different transaction parameters" in conflict.json()["detail"]
    with api.sessions() as db:
        transaction = db.query(Transaction).one()
        for account_id in api.account_ids:
            expected = Decimal("100.00")
            if account_id == transaction.account_id:
                expected -= transaction.amount
            assert db.get(Account, account_id).balance == expected
