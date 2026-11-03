from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from apps.accounts.models import Account
from apps.budgets.schemas import BudgetCreate, BudgetUpdate
from apps.budgets.services import BudgetService
from apps.exchange.models import ExchangeRate
from apps.transactions.models import Transaction
from apps.users.models import User
from core.constants.budgets import BudgetPeriod, BudgetStatus
from core.constants.currency import Currency
from core.constants.transaction import TransactionType


def _create_user(db_session, email: str = "budget-owner@example.com"):
    user = User(email=email, is_active=True, is_verified=True)
    user.set_password("secret123")
    db_session.add(user)
    db_session.flush()
    return user


def _add_transaction(
    db_session,
    user,
    *,
    category,
    amount,
    created_at,
    transaction_type=TransactionType.EXPENSE,
    currency="EUR",
):
    account = Account(
        user_id=user.id,
        name=f"Account {created_at.isoformat()}",
        balance=Decimal("1000.00"),
        currency=currency,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    db_session.add(
        Transaction(
            user_id=user.id,
            account_id=account.id,
            type=transaction_type,
            amount=amount,
            balance_after=Decimal("1000.00"),
            currency=currency,
            category=category,
            created_at=created_at,
        )
    )
    db_session.flush()


def test_weekly_budget_spending_sums_only_current_week_expenses(db_session):
    user = _create_user(db_session)
    as_of = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    _add_transaction(
        db_session,
        user,
        category=" Food ",
        amount=Decimal("10.00"),
        created_at=datetime(2026, 10, 4, 23, 59),
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("20.00"),
        created_at=datetime(2026, 10, 5, 0, 0),
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("30.00"),
        created_at=datetime(2026, 10, 11, 23, 59),
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("40.00"),
        created_at=datetime(2026, 10, 12, 0, 0),
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("50.00"),
        created_at=datetime(2026, 10, 6, 12),
        transaction_type=TransactionType.INCOME,
    )
    another_user = _create_user(db_session, email="another@example.com")
    _add_transaction(
        db_session,
        another_user,
        category="food",
        amount=Decimal("500.00"),
        created_at=datetime(2026, 10, 6, 12),
    )
    db_session.flush()

    budget = BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="food",
            limit=Decimal("100.00"),
            period=BudgetPeriod.WEEKLY,
        ),
        db_session,
    )
    spent = BudgetService.get_budget_spent_amount(
        user.id, budget, db_session, as_of=as_of
    )

    assert spent == Decimal("50.00")


def test_budget_spending_is_converted_to_budget_currency(db_session, monkeypatch):
    as_of = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return as_of.astimezone(tz) if tz else as_of.replace(tzinfo=None)

    monkeypatch.setattr("apps.budgets.services.datetime", FixedDateTime)
    
    user = _create_user(db_session)
    budget = BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="food",
            limit=Decimal("100.00"),
            period=BudgetPeriod.MONTHLY,
            currency=Currency.USD,
        ),
        db_session,
    )
    db_session.add(
        ExchangeRate(
            from_currency=Currency.EUR,
            to_currency=Currency.USD,
            rate=Decimal("1.10"),
        )
    )
    db_session.add(
        ExchangeRate(
            from_currency=Currency.USD,
            to_currency=Currency.EUR,
            rate=Decimal("0.90909091"),
        )
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("25.00"),
        created_at=datetime(2026, 10, 6, 12),
    )
    db_session.commit()

    spent = BudgetService.get_budget_spent_amount(
        user.id,
        budget,
        db_session,
        as_of=as_of,
    )

    assert budget.currency == Currency.USD.value
    assert spent == Decimal("27.50")
    checks = BudgetService.check_budget_usage(
        user.id,
        "food",
        Decimal("60.00"),
        db_session,
        period=BudgetPeriod.MONTHLY,
        currency=Currency.EUR,
    )
    assert checks[0]["currency"] == Currency.USD
    assert checks[0]["warning"] == (
        "Budget usage has reached 80% of the limit"
    )

    warning = BudgetService.get_expense_budget_warning(
        user.id,
        "food",
        Decimal("60.00"),
        Currency.EUR,
        db_session,
    )
    assert warning == "Budget usage reached 80% for category 'food'"
    stats = BudgetService.get_budget_statistics(user.id, db_session)
    assert stats["currency"] == Currency.EUR
    assert stats["total_spent"] == Decimal("25.00")


def test_create_budget_normalizes_category_and_rejects_duplicates(db_session):
    user = _create_user(db_session)
    payload = BudgetCreate(
        category=" Groceries ",
        limit=Decimal("500.00"),
        period=BudgetPeriod.MONTHLY,
    )

    created = BudgetService.create_budget(user.id, payload, db_session)
    assert created.category == "groceries"
    assert created.limit == Decimal("500.00")

    with pytest.raises(HTTPException) as exc:
        BudgetService.create_budget(user.id, payload, db_session)

    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail


def test_update_budget_can_change_limit_currency(db_session):
    user = _create_user(db_session)
    budget = BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="food",
            limit=Decimal("100.00"),
            period=BudgetPeriod.MONTHLY,
        ),
        db_session,
    )

    updated = BudgetService.update_budget(
        user.id,
        budget.id,
        BudgetUpdate(currency=Currency.USD),
        db_session,
    )

    assert updated.currency == Currency.USD.value


def test_budget_summary_uses_current_period_transaction_spending(
    db_session,
):
    user = _create_user(db_session)
    budget = BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="Transport",
            limit=Decimal("100.00"),
            period=BudgetPeriod.MONTHLY,
        ),
        db_session,
    )

    _add_transaction(
        db_session,
        user,
        category="transport",
        amount=Decimal("80.00"),
        created_at=datetime(2026, 10, 5, 9),
    )
    summary = BudgetService.get_budget_summary(
        user.id,
        budget,
        db_session,
        as_of=datetime(2026, 10, 7, 12, tzinfo=timezone.utc),
    )
    assert summary["spent_amount"] == Decimal("80.00")
    assert summary["status"] == BudgetStatus.WARNING

    _add_transaction(
        db_session,
        user,
        category="transport",
        amount=Decimal("30.00"),
        created_at=datetime(2026, 10, 6, 9),
    )
    summary = BudgetService.get_budget_summary(
        user.id,
        budget,
        db_session,
        as_of=datetime(2026, 10, 7, 12, tzinfo=timezone.utc),
    )
    assert summary["spent_amount"] == Decimal("110.00")
    assert summary["status"] == BudgetStatus.EXCEEDED


def test_budget_statistics_counts_statuses_correctly(db_session):
    user = _create_user(db_session)

    BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="food",
            limit=Decimal("100.00"),
            period=BudgetPeriod.MONTHLY,
        ),
        db_session,
    )
    BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="health",
            limit=Decimal("200.00"),
            period=BudgetPeriod.MONTHLY,
        ),
        db_session,
    )
    BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="travel",
            limit=Decimal("50.00"),
            period=BudgetPeriod.MONTHLY,
        ),
        db_session,
    )

    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("50.00"),
        created_at=datetime(2026, 10, 5, 8),
    )
    _add_transaction(
        db_session,
        user,
        category="health",
        amount=Decimal("180.00"),
        created_at=datetime(2026, 10, 6, 8),
    )
    _add_transaction(
        db_session,
        user,
        category="travel",
        amount=Decimal("60.00"),
        created_at=datetime(2026, 10, 6, 9),
    )

    stats = BudgetService.get_budget_statistics(
        user.id,
        db_session,
        as_of=datetime(2026, 10, 7, 12, tzinfo=timezone.utc),
    )

    assert stats["total_budgets"] == 3
    assert stats["total_limit"] == Decimal("350.00")
    assert stats["total_spent"] == Decimal("290.00")
    assert stats["status_counts"][BudgetStatus.NORMAL.value] == 1
    assert stats["status_counts"][BudgetStatus.WARNING.value] == 1
    assert stats["status_counts"][BudgetStatus.EXCEEDED.value] == 1


def test_statistics_count_overlapping_budget_expenses_once(db_session):
    user = _create_user(db_session)
    for period in [BudgetPeriod.WEEKLY, BudgetPeriod.MONTHLY]:
        BudgetService.create_budget(
            user.id,
            BudgetCreate(category="food", limit="100.00", period=period),
            db_session,
        )
    _add_transaction(
        db_session, user, category=" FOOD ", amount=Decimal("25.00"),
        created_at=datetime(2026, 10, 6, 12),
    )
    stats = BudgetService.get_budget_statistics(
        user.id, db_session, as_of=datetime(2026, 10, 7, tzinfo=timezone.utc)
    )
    assert stats["total_spent"] == Decimal("25.00")
    # Limits, remaining allowances and statuses still describe each budget.
    assert stats["total_limit"] == Decimal("200.00")
    assert stats["total_remaining"] == Decimal("150.00")
    assert stats["total_budgets"] == 2
    assert stats["status_counts"][BudgetStatus.NORMAL.value] == 2


def test_statistics_use_union_of_current_budget_windows(db_session):
    user = _create_user(db_session)
    for period in [BudgetPeriod.WEEKLY, BudgetPeriod.MONTHLY]:
        BudgetService.create_budget(
            user.id,
            BudgetCreate(category="food", limit="1000.00", period=period),
            db_session,
        )
    # On October 1 the current week begins in September. Keep its expenses
    # and monthly-only expenses, count overlaps once, exclude both end bounds.
    for created_at, amount in [
        (datetime(2026, 9, 27, 23, 59, 59), "999.00"),
        (datetime(2026, 9, 28), "10.00"),
        (datetime(2026, 9, 30, 12), "15.00"),
        (datetime(2026, 10, 1), "20.00"),
        (datetime(2026, 10, 4, 23, 59, 59), "25.00"),
        (datetime(2026, 10, 5), "30.00"),
        (datetime(2026, 10, 31, 23, 59, 59), "35.00"),
        (datetime(2026, 11, 1), "999.00"),
    ]:
        _add_transaction(
            db_session, user, category="food", amount=Decimal(amount),
            created_at=created_at,
        )
    stats = BudgetService.get_budget_statistics(
        user.id, db_session, as_of=datetime(2026, 10, 1, tzinfo=timezone.utc)
    )
    assert stats["total_spent"] == Decimal("135.00")


def test_statistics_convert_unique_expenses_and_keep_user_category_scope(
    db_session,
):
    user = _create_user(db_session)
    other = _create_user(db_session, "other-statistics@example.com")
    for source, target, rate in [
        (Currency.USD, Currency.EUR, "0.5"),
        (Currency.EUR, Currency.USD, "2"),
        (Currency.GBP, Currency.EUR, "2"),
        (Currency.EUR, Currency.GBP, "0.5"),
        (Currency.USD, Currency.GBP, "0.25"),
        (Currency.GBP, Currency.USD, "4"),
    ]:
        db_session.add(ExchangeRate(
            from_currency=source, to_currency=target, rate=Decimal(rate),
        ))
    for period, currency in [
        (BudgetPeriod.WEEKLY, Currency.USD),
        (BudgetPeriod.MONTHLY, Currency.GBP),
    ]:
        BudgetService.create_budget(
            user.id, BudgetCreate(
                category="food", limit="100.00", period=period,
                currency=currency,
            ), db_session,
        )
    BudgetService.create_budget(
        other.id, BudgetCreate(category="travel", limit="100.00"), db_session
    )
    date = datetime(2026, 10, 6, 12)
    for currency in ["USD", "EUR", "EUR"]:
        _add_transaction(
            db_session, user, category=" Food ", amount=Decimal("20.00"),
            created_at=date, currency=currency,
        )
    for owner, category, kind in [
        (user, "travel", TransactionType.EXPENSE),
        (user, None, TransactionType.EXPENSE),
        (other, "food", TransactionType.EXPENSE),
        (user, "food", TransactionType.INCOME),
        (user, "food", TransactionType.CONVERSION),
    ]:
        _add_transaction(
            db_session, owner, category=category, amount=Decimal("999.00"),
            created_at=date, transaction_type=kind,
        )
    stats = BudgetService.get_budget_statistics(
        user.id, db_session, as_of=datetime(2026, 10, 7, tzinfo=timezone.utc)
    )
    assert stats["currency"] == Currency.EUR
    assert stats["total_spent"] == Decimal("50.00")


def test_statistics_without_budgets_do_not_include_unbudgeted_expenses(
    db_session,
):
    user = _create_user(db_session)
    _add_transaction(
        db_session, user, category="food", amount=Decimal("25.00"),
        created_at=datetime(2026, 10, 6, 12),
    )
    stats = BudgetService.get_budget_statistics(
        user.id, db_session, as_of=datetime(2026, 10, 7, tzinfo=timezone.utc)
    )
    assert stats["total_budgets"] == 0
    assert stats["total_spent"] == Decimal("0")
    assert stats["total_limit"] == Decimal("0")
    assert stats["total_remaining"] == Decimal("0")


def test_monthly_budget_spending_uses_calendar_month(db_session):
    user = _create_user(db_session)
    budget = BudgetService.create_budget(
        user.id,
        BudgetCreate(
            category="food",
            limit=Decimal("500.00"),
            period=BudgetPeriod.MONTHLY,
        ),
        db_session,
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("25.00"),
        created_at=datetime(2026, 9, 30, 23, 59),
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("75.00"),
        created_at=datetime(2026, 10, 1, 0, 0),
    )
    _add_transaction(
        db_session,
        user,
        category="food",
        amount=Decimal("100.00"),
        created_at=datetime(2026, 11, 1, 0, 0),
    )

    summary = BudgetService.get_budget_summary(
        user.id,
        budget,
        db_session,
        as_of=datetime(2026, 10, 7, 12, tzinfo=timezone.utc),
    )

    assert summary["spent_amount"] == Decimal("75.00")


def test_budget_api_returns_spending_aggregated_from_transactions(client):
    credentials = {"email": "budget-api@example.com", "password": "secret123"}
    registration = client.post("/api/v1/auth/register", json=credentials)
    assert registration.status_code == 201, registration.text
    login = client.post("/api/v1/auth/login", data=credentials)
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    account = client.post(
        "/api/v1/accounts/create",
        json={"name": "Budget account", "currency": "EUR"},
        headers=headers,
    )
    assert account.status_code == 201, account.text
    budget = client.post(
        "/api/v1/budgets/create",
        json={"category": "food", "limit": "100.00", "period": "monthly"},
        headers=headers,
    )
    assert budget.status_code == 201, budget.text

    weekly_budget = client.post(
        "/api/v1/budgets/create",
        json={"category": "food", "limit": "100.00", "period": "weekly"},
        headers=headers,
    )
    assert weekly_budget.status_code == 201, weekly_budget.text

    income = client.post(
        "/api/v1/transactions/",
        json={
            "account_id": account.json()["id"],
            "type": "income",
            "amount": "100.00",
            "currency": "EUR",
        },
        headers={**headers, "Idempotency-Key": "budget-income"},
    )
    assert income.status_code == 201, income.text

    transaction = client.post(
        "/api/v1/transactions/",
        json={
            "account_id": account.json()["id"],
            "type": "expense",
            "amount": "80.00",
            "currency": "EUR",
            "category": " Food ",
        },
        headers={**headers, "Idempotency-Key": "budget-expense"},
    )
    assert transaction.status_code == 201, transaction.text

    budgets = client.get("/api/v1/budgets/", headers=headers)
    assert budgets.status_code == 200, budgets.text
    assert Decimal(str(budgets.json()[0]["spent_amount"])) == Decimal("80.00")
    assert budgets.json()[0]["status"] == BudgetStatus.WARNING.value

    statistics = client.get(
        "/api/v1/budgets/statistics", headers=headers
    )
    assert statistics.status_code == 200, statistics.text
    assert Decimal(str(statistics.json()["total_spent"])) == Decimal("80.00")
