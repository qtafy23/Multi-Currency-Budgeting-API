from decimal import Decimal

import pytest
from fastapi import HTTPException

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
