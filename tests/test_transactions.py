from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apps.accounts.models import Account
from apps.transactions.models import Transaction
from apps.transactions.schemas import TransactionCreate
from apps.transactions.services import TransactionService
from apps.users.models import User
from core.constants.currency import Currency
from core.constants.transaction import TransactionType


def _create_user_and_account(
    db_session,
    email: str = "alice@example.com",
    balance: Decimal = Decimal("100.00"),
):
    user = User(email=email, is_active=True, is_verified=True)
    user.set_password("secret123")
    db_session.add(user)
    db_session.flush()

    account = Account(
        user_id=user.id,
        name="Main account",
        balance=balance,
        currency=Currency.USD.value,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    return user, account


def test_create_transaction_updates_balance_and_persists_record(db_session):
    _, account = _create_user_and_account(db_session)
    payload = TransactionCreate(
        account_id=account.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("15.50"),
        currency=Currency.USD,
        category="groceries",
        note="Weekly shop",
    )

    transaction, created = TransactionService.create_transaction(
        db_session, payload, account.user_id, "key-1"
    )

    assert created is True
    assert transaction.amount == Decimal("15.50")
    assert transaction.balance_after == Decimal("84.50")
    assert transaction.currency == Currency.USD.value
    assert db_session.query(Transaction).count() == 1
    assert db_session.query(Account).get(account.id).balance == Decimal(
        "84.50"
    )


def test_create_transaction_is_idempotent_for_same_key(db_session):
    _, account = _create_user_and_account(db_session)
    payload = TransactionCreate(
        account_id=account.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("10.00"),
        currency=Currency.USD,
        category="transport",
    )

    first, created_first = TransactionService.create_transaction(
        db_session, payload, account.user_id, "same-key"
    )
    second, created_second = TransactionService.create_transaction(
        db_session, payload, account.user_id, "same-key"
    )

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert db_session.query(Transaction).count() == 1


def test_create_transaction_rejects_insufficient_balance(db_session):
    _, account = _create_user_and_account(db_session, balance=Decimal("20.00"))
    payload = TransactionCreate(
        account_id=account.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("25.00"),
        currency=Currency.USD,
        category="rent",
    )

    with pytest.raises(HTTPException) as exc:
        TransactionService.create_transaction(
            db_session, payload, account.user_id, "overdraft-key"
        )

    assert exc.value.status_code == 400
    assert "Insufficient account balance" in str(exc.value.detail)


def test_key_is_shared_between_accounts_of_one_user(db_session):
    user, first_account = _create_user_and_account(db_session)
    second_account = Account(
        user_id=user.id, name="Second", balance=Decimal("100.00"),
        currency="USD", is_active=True,
    )
    db_session.add(second_account)
    db_session.flush()
    for account in [first_account, second_account]:
        payload = TransactionCreate(
            account_id=account.id, type=TransactionType.EXPENSE,
            amount=Decimal("10.00"), currency=Currency.USD,
        )
        if account is first_account:
            TransactionService.create_transaction(
                db_session, payload, user.id, "shared-key"
            )
        else:
            with pytest.raises(HTTPException) as exc:
                TransactionService.create_transaction(
                    db_session, payload, user.id, "shared-key"
                )
            assert exc.value.status_code == 409
    db_session.refresh(second_account)
    assert second_account.balance == Decimal("100.00")
    assert db_session.query(Transaction).count() == 1


def test_database_rejects_duplicate_key_for_user_across_accounts(db_session):
    user, account = _create_user_and_account(db_session)
    second_account = Account(
        user_id=user.id, name="Second", currency="USD", balance=0,
    )
    db_session.add(second_account)
    db_session.commit()
    values = dict(
        user_id=user.id, idempotency_key="duplicate",
        type=TransactionType.INCOME, amount=Decimal("1.00"),
        balance_after=Decimal("1.00"), currency="USD",
    )
    db_session.add(Transaction(account_id=account.id, **values))
    db_session.commit()
    db_session.add(Transaction(account_id=second_account.id, **values))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.query(Transaction).count() == 1


def test_transactions_without_key_are_not_deduplicated(db_session):
    user, account = _create_user_and_account(db_session)
    payload = TransactionCreate(
        account_id=account.id, type=TransactionType.EXPENSE,
        amount=Decimal("10.00"), currency=Currency.USD,
    )
    for _ in range(2):
        _, created = TransactionService.create_transaction(
            db_session, payload, user.id, None
        )
        assert created is True
    db_session.refresh(account)
    assert account.balance == Decimal("80.00")
    assert db_session.query(Transaction).count() == 2


def test_same_key_with_changed_payload_does_not_change_balance(db_session):
    user, account = _create_user_and_account(db_session)
    payload = TransactionCreate(
        account_id=account.id, type=TransactionType.EXPENSE,
        amount=Decimal("10.00"), currency=Currency.USD,
    )
    TransactionService.create_transaction(
        db_session, payload, user.id, "shared-key"
    )
    payload.amount = Decimal("20.00")
    with pytest.raises(HTTPException) as exc:
        TransactionService.create_transaction(
            db_session, payload, user.id, "shared-key"
        )
    assert exc.value.status_code == 409
    db_session.refresh(account)
    assert account.balance == Decimal("90.00")


def test_api_accepts_same_key_for_different_authenticated_users(client):
    transaction_ids = []
    for email in ["api-alice@example.com", "api-bob@example.com"]:
        credentials = {"email": email, "password": "secret123"}
        assert client.post(
            "/api/v1/auth/register", json=credentials
        ).status_code == 201
        login = client.post("/api/v1/auth/login", data=credentials)
        assert login.status_code == 200, login.text
        headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "Idempotency-Key": "shared-api-key",
        }
        account = client.post(
            "/api/v1/accounts/create",
            json={"name": "Main", "currency": "USD"}, headers=headers,
        )
        assert account.status_code == 201, account.text
        payload = {
            "account_id": account.json()["id"], "type": "income",
            "amount": "10.00", "currency": "USD",
        }
        first = client.post(
            "/api/v1/transactions/", json=payload, headers=headers
        )
        assert first.status_code == 201, first.text
        repeated = client.post(
            "/api/v1/transactions/", json=payload, headers=headers
        )
        assert repeated.status_code == 200, repeated.text
        assert first.json()["id"] == repeated.json()["id"]
        balance = client.get(
            f"/api/v1/accounts/{account.json()['id']}", headers=headers
        )
        assert Decimal(balance.json()["balance"]) == Decimal("10.00")
        transaction_ids.append(first.json()["id"])
    assert transaction_ids[0] != transaction_ids[1]
