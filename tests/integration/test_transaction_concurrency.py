from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Lock
from time import monotonic, sleep

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from apps.accounts.models import Account
from apps.transactions.models import Transaction
from apps.transactions.schemas import TransactionCreate
from apps.transactions.services import TransactionService
from apps.users.models import User
from core.constants.currency import Currency
from core.constants.transaction import TransactionType

pytestmark = pytest.mark.postgres


def _seed(sessions):
    with sessions() as db:
        user = User(
            email="concurrency@example.com", hashed_password="unused",
            is_active=True, is_verified=True,
        )
        db.add(user)
        db.flush()
        account = Account(
            user_id=user.id, name="Concurrent account",
            balance=Decimal("100.00"), currency="EUR", is_active=True,
        )
        db.add(account)
        db.commit()
        return user.id, account.id


def _payload(account_id, kind, amount):
    return TransactionCreate(
        account_id=account_id, type=kind,
        amount=Decimal(amount), currency=Currency.EUR,
    )


def _concurrent(sessions, monkeypatch, user_id, account_id, payload, keys):
    ready = Barrier(2, timeout=10)
    guard = Lock()
    initial_sessions = set()
    worker_pids = []
    original = TransactionService.find_idempotent_transaction

    def synchronized_lookup(db, *args):
        result = original(db, *args)
        with guard:
            first_lookup = db not in initial_sessions
            initial_sessions.add(db)
        if first_lookup:
            pid = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            with guard:
                worker_pids.append(pid)
            # Both requests must observe the pre-insert state.
            ready.wait()
        return result

    monkeypatch.setattr(
        TransactionService, "find_idempotent_transaction",
        staticmethod(synchronized_lookup),
    )

    def request(key):
        with sessions() as db:
            try:
                transaction, created = TransactionService.create_transaction(
                    db, payload, user_id, key,
                )
                return transaction.id, created
            except HTTPException as exc:
                db.rollback()
                return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        with sessions() as holder:
            holder.query(Account).filter_by(id=account_id).with_for_update().one()
            futures = [pool.submit(request, key) for key in keys]
            try:
                deadline = monotonic() + 8
                with sessions() as observer:
                    while monotonic() < deadline:
                        with guard:
                            pids = list(worker_pids)
                        blocked = observer.execute(
                            text(
                                "SELECT count(*) "
                                "FROM unnest(CAST(:pids AS int[])) AS pid "
                                "WHERE cardinality(pg_blocking_pids(pid)) > 0"
                            ),
                            {"pids": pids}
                        ).scalar_one()
                        if blocked == 2:
                            break
                        sleep(0.02)
                    else:
                        pytest.fail("Both requests must wait for the account row lock")
            finally:
                holder.rollback()
        return [future.result(timeout=20) for future in futures]


def _state(sessions, account_id):
    with sessions() as db:
        return (
            db.get(Account, account_id).balance,
            db.query(Transaction).filter_by(account_id=account_id).count(),
        )


def test_concurrent_expenses_cannot_overdraw(postgres_sessions, monkeypatch):
    user_id, account_id = _seed(postgres_sessions)
    results = _concurrent(
        postgres_sessions, monkeypatch, user_id, account_id,
        _payload(account_id, TransactionType.EXPENSE, "80"), ["expense-1", "expense-2"],
    )
    errors = [result for result in results if isinstance(result, HTTPException)]
    assert len(errors) == 1
    assert errors[0].status_code == 400
    assert errors[0].detail == "Insufficient account balance"
    assert _state(postgres_sessions, account_id) == (Decimal("20.00"), 1)


def test_concurrent_incomes_preserve_both_updates(postgres_sessions, monkeypatch):
    user_id, account_id = _seed(postgres_sessions)
    results = _concurrent(
        postgres_sessions, monkeypatch, user_id, account_id,
        _payload(account_id, TransactionType.INCOME, "30"), ["income-1", "income-2"],
    )
    assert all(not isinstance(result, HTTPException) for result in results)
    assert all(created for _, created in results)
    assert len({transaction_id for transaction_id, _ in results}) == 2
    assert _state(postgres_sessions, account_id) == (Decimal("160.00"), 2)


def test_concurrent_same_key_changes_balance_once(postgres_sessions, monkeypatch):
    user_id, account_id = _seed(postgres_sessions)
    results = _concurrent(
        postgres_sessions, monkeypatch, user_id, account_id,
        _payload(account_id, TransactionType.EXPENSE, "30"), ["same-key", "same-key"],
    )
    assert all(not isinstance(result, HTTPException) for result in results)
    assert sorted(created for _, created in results) == [False, True]
    assert len({transaction_id for transaction_id, _ in results}) == 1
    assert _state(postgres_sessions, account_id) == (Decimal("70.00"), 1)


def test_insert_failure_rolls_back_balance(postgres_sessions):
    user_id, account_id = _seed(postgres_sessions)
    with postgres_sessions() as db:
        db.execute(text(
            "ALTER TABLE transactions ADD CONSTRAINT reject_test_amount "
            "CHECK (amount <> 13)"
        ))
        db.commit()
        with pytest.raises(HTTPException) as exc:
            TransactionService.create_transaction(
                db, _payload(account_id, TransactionType.EXPENSE, "13"),
                user_id, "failed-insert",
            )
        assert exc.value.status_code == 409
        # The service has rolled back and the same session is usable again.
        assert db.get(Account, account_id).balance == Decimal("100.00")
        assert db.query(Transaction).count() == 0
    assert _state(postgres_sessions, account_id) == (Decimal("100.00"), 0)
