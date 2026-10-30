from decimal import Decimal

import pytest
from fastapi import HTTPException

from apps.accounts.models import Account
from apps.accounts.services import AccountService
from apps.exchange.models import ExchangeRate
from apps.transactions.models import Transaction
from apps.users.models import User
from core.constants.currency import Currency
from core.constants.transaction import TransactionType


def _create_user_and_account(db_session):
    user = User(
        email="conversion@example.com",
        is_active=True,
        is_verified=True,
    )
    user.set_password("secret123")
    db_session.add(user)
    db_session.flush()

    account = Account(
        user_id=user.id,
        name="Conversion account",
        balance=Decimal("1000.00"),
        currency=Currency.USD.value,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()

    return user, account


def test_convert_account_currency(db_session):
    user, account = _create_user_and_account(db_session)

    db_session.add(
        ExchangeRate(
            from_currency=Currency.USD,
            to_currency=Currency.EUR,
            rate=Decimal("0.92000000"),
        )
    )
    db_session.commit()

    result = AccountService.convert_currency(
        account_id=account.id,
        user_id=user.id,
        target_currency=Currency.EUR,
        db=db_session,
    )
    transaction = result["transaction"]

    db_session.refresh(account)

    assert account.currency == Currency.EUR.value
    assert account.balance == Decimal("920.00")

    assert transaction.type == TransactionType.CONVERSION
    assert transaction.original_amount == Decimal("1000.00")
    assert transaction.converted_amount == Decimal("920.00")
    assert transaction.exchange_rate == Decimal("0.92000000")

    conversions = (
        db_session.query(Transaction)
        .filter(
            Transaction.account_id == account.id,
            Transaction.type == TransactionType.CONVERSION,
        )
        .all()
    )
    assert len(conversions) == 1


def test_convert_account_to_same_currency_fails(db_session):
    user, account = _create_user_and_account(db_session)

    with pytest.raises(HTTPException) as exc:
        AccountService.convert_currency(
            account_id=account.id,
            user_id=user.id,
            target_currency=Currency.USD,
            db=db_session,
        )

    assert exc.value.status_code == 400
    assert account.balance == Decimal("1000.00")
    assert account.currency == Currency.USD.value


def test_convert_another_users_account_fails(db_session):
    user, account = _create_user_and_account(db_session)

    with pytest.raises(HTTPException) as exc:
        AccountService.convert_currency(
            account_id=account.id,
            user_id=user.id + 100,
            target_currency=Currency.EUR,
            db=db_session,
        )

    assert exc.value.status_code == 404
    assert account.balance == Decimal("1000.00")
    assert account.currency == Currency.USD.value


def test_convert_without_exchange_rate_fails(db_session):
    user, account = _create_user_and_account(db_session)

    with pytest.raises(HTTPException) as exc:
        AccountService.convert_currency(
            account_id=account.id,
            user_id=user.id,
            target_currency=Currency.GBP,
            db=db_session,
        )

    assert exc.value.status_code == 404
    assert account.balance == Decimal("1000.00")
    assert account.currency == Currency.USD.value
    assert db_session.query(Transaction).count() == 0
