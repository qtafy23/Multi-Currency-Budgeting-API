from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.accounts.models import Account, AccountEvent
from apps.budgets.models import Budget
from apps.exchange.models import ExchangeRate
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.users.services import AuthenticationService
from core.constants.budgets import BudgetPeriod
from core.constants.currency import Currency
from core.constants.transaction import TransactionType


@pytest.fixture
def wallet(client, db_session):
    user = User(
        email="rate-policy@example.com",
        hashed_password="unused",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    account = Account(
        user_id=user.id,
        name="Policy test",
        balance=Decimal("100.00"),
        currency="USD",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    token = AuthenticationService.create_tokens(user).access_token
    client.headers["Authorization"] = f"Bearer {token}"
    return account.id


def seed_rate(db, state, source=Currency.USD, target=Currency.EUR):
    if state == "missing":
        return
    stamp = datetime.now(timezone.utc).replace(tzinfo=None)
    if state == "stale":
        stamp -= timedelta(hours=49)
    db.add(
        ExchangeRate(
            from_currency=source,
            to_currency=target,
            rate=Decimal("0.9"),
            updated_at=stamp,
        )
    )
    db.commit()


def assert_rate_failure(response, state):
    assert response.status_code == 503, response.text
    expected = (
        "exchange_rate_unavailable"
        if state == "missing"
        else "exchange_rate_stale"
    )
    assert response.json()["detail"]["code"] == expected


@pytest.mark.parametrize("state", ["missing", "stale"])
@pytest.mark.parametrize("operation", ["transaction", "account_conversion"])
def test_currency_write_failure_preserves_money(
    client,
    db_session,
    wallet,
    state,
    operation,
):
    if operation == "transaction":
        seed_rate(db_session, state, Currency.EUR, Currency.USD)
        response = client.post(
            "/api/v1/transactions/",
            headers={"Idempotency-Key": "failed-conversion"},
            json={
                "account_id": wallet,
                "type": "expense",
                "amount": "10.00",
                "currency": "EUR",
            },
        )
    else:
        seed_rate(db_session, state)
        response = client.post(
            f"/api/v1/accounts/{wallet}/convert-currency",
            json={"target_currency": "EUR"},
        )
    assert_rate_failure(response, state)
    db_session.expire_all()
    account = db_session.get(Account, wallet)
    assert account.balance == Decimal("100.00")
    assert account.currency == "USD"
    assert db_session.query(Transaction).count() == 0
    assert db_session.query(AccountEvent).count() == 0


@pytest.mark.parametrize("state", ["missing", "stale"])
def test_same_currency_write_needs_no_rate(
    client,
    db_session,
    wallet,
    state,
):
    seed_rate(db_session, state)
    response = client.post(
        "/api/v1/transactions/",
        headers={"Idempotency-Key": "same-currency"},
        json={
            "account_id": wallet,
            "type": "expense",
            "amount": "10.00",
            "currency": "USD",
        },
    )
    assert response.status_code == 201, response.text
    db_session.expire_all()
    assert db_session.get(Account, wallet).balance == Decimal("90.00")


def test_completed_request_replays_after_rate_expires_or_disappears(
    client,
    db_session,
    wallet,
):
    seed_rate(db_session, "fresh", Currency.EUR, Currency.USD)
    payload = {
        "account_id": wallet,
        "type": "expense",
        "amount": "10.00",
        "currency": "EUR",
    }
    headers = {"Idempotency-Key": "completed"}
    first = client.post("/api/v1/transactions/", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    rate = db_session.query(ExchangeRate).one()
    rate.updated_at = datetime.now(timezone.utc) - timedelta(hours=49)
    db_session.commit()
    for remove in [False, True]:
        if remove:
            db_session.delete(rate)
            db_session.commit()
        repeated = client.post(
            "/api/v1/transactions/", json=payload, headers=headers
        )
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["id"] == first.json()["id"]
    db_session.expire_all()
    assert db_session.get(Account, wallet).balance == Decimal("91.00")
    assert db_session.query(Transaction).count() == 1


@pytest.mark.parametrize("state", ["missing", "stale", "fresh"])
def test_statistics_require_a_usable_rate_for_the_complete_total(
    client,
    db_session,
    wallet,
    state,
):
    account = db_session.get(Account, wallet)
    db_session.add(
        Budget(
            user_id=account.user_id,
            category="food",
            limit=Decimal("100.00"),
            currency="EUR",
            period=BudgetPeriod.MONTHLY,
        )
    )
    db_session.add(
        Transaction(
            user_id=account.user_id,
            account_id=wallet,
            type=TransactionType.EXPENSE,
            amount=Decimal("10.00"),
            balance_after=Decimal("90.00"),
            currency="USD",
            category="food",
        )
    )
    account.balance = Decimal("90.00")
    db_session.commit()
    seed_rate(db_session, state)
    response = client.get("/api/v1/budgets/statistics")
    if state == "fresh":
        assert response.status_code == 200, response.text
        assert Decimal(response.json()["total_spent"]) == Decimal("9.00")
    else:
        assert_rate_failure(response, state)
        assert "total_spent" not in response.json()
    assert db_session.query(Transaction).count() == 1


@pytest.mark.parametrize("state", ["missing", "stale"])
def test_budget_check_failure_also_prevents_same_currency_spending(
    client,
    db_session,
    wallet,
    state,
):
    account = db_session.get(Account, wallet)
    db_session.add(
        Budget(
            user_id=account.user_id,
            category="food",
            limit=Decimal("100.00"),
            currency="EUR",
            period=BudgetPeriod.MONTHLY,
        )
    )
    db_session.commit()
    seed_rate(db_session, state)
    response = client.post(
        "/api/v1/transactions/",
        headers={"Idempotency-Key": "budget-check"},
        json={
            "account_id": wallet,
            "type": "expense",
            "amount": "10.00",
            "currency": "USD",
            "category": "food",
        },
    )
    assert_rate_failure(response, state)
    db_session.expire_all()
    assert db_session.get(Account, wallet).balance == Decimal("100.00")
    assert db_session.query(Transaction).count() == 0


def test_zero_balance_currency_change_needs_no_rate(
    client,
    db_session,
    wallet,
):
    account = db_session.get(Account, wallet)
    account.balance = Decimal("0.00")
    db_session.commit()
    response = client.post(
        f"/api/v1/accounts/{wallet}/convert-currency",
        json={"target_currency": "EUR"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["converted"] is False
    assert db_session.query(Transaction).count() == 0
    assert db_session.query(AccountEvent).count() == 1
