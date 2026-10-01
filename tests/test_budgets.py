from decimal import Decimal

import pytest
from fastapi import HTTPException

from apps.budgets.schemas import BudgetCreate
from apps.budgets.services import BudgetService
from apps.users.models import User
from core.constants.budgets import BudgetPeriod, BudgetStatus


def _create_user(db_session, email: str = "budget-owner@example.com"):
    user = User(email=email, is_active=True, is_verified=True)
    user.set_password("secret123")
    db_session.add(user)
    db_session.flush()
    return user


def test_create_budget_normalizes_category_and_rejects_duplicates(db_session):
    user = _create_user(db_session)
    payload = BudgetCreate(category=" Groceries ", limit=Decimal("500.00"), period=BudgetPeriod.MONTHLY)

    created = BudgetService.create_budget(user.id, payload, db_session)
    assert created.category == "groceries"
    assert created.limit == Decimal("500.00")

    with pytest.raises(HTTPException) as exc:
        BudgetService.create_budget(user.id, payload, db_session)

    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail


def test_update_budget_spent_amount_tracks_warning_and_exceeded_thresholds(db_session):
    user = _create_user(db_session)
    budget = BudgetService.create_budget(
        user.id,
        BudgetCreate(category="Transport", limit=Decimal("100.00"), period=BudgetPeriod.MONTHLY),
        db_session,
    )

    first_warning = BudgetService.update_budget_spent_amount(user.id, "Transport", Decimal("80.00"), db_session)
    assert first_warning == "Budget usage reached 80% for category 'Transport'"
    assert budget.spent_amount == Decimal("80.00")
    assert budget.status == BudgetStatus.WARNING

    second_warning = BudgetService.update_budget_spent_amount(user.id, "Transport", Decimal("30.00"), db_session)
    assert second_warning == "Budget limit exceeded for category 'Transport'"
    assert budget.spent_amount == Decimal("110.00")
    assert budget.status == BudgetStatus.EXCEEDED


def test_budget_statistics_counts_statuses_correctly(db_session):
    user = _create_user(db_session)

    BudgetService.create_budget(user.id, BudgetCreate(category="food", limit=Decimal("100.00"), period=BudgetPeriod.MONTHLY), db_session)
    BudgetService.create_budget(user.id, BudgetCreate(category="health", limit=Decimal("200.00"), period=BudgetPeriod.MONTHLY), db_session)
    BudgetService.create_budget(user.id, BudgetCreate(category="travel", limit=Decimal("50.00"), period=BudgetPeriod.MONTHLY), db_session)

    BudgetService.update_budget_spent_amount(user.id, "food", Decimal("50.00"), db_session)
    BudgetService.update_budget_spent_amount(user.id, "health", Decimal("180.00"), db_session)
    BudgetService.update_budget_spent_amount(user.id, "travel", Decimal("60.00"), db_session)

    stats = BudgetService.get_budget_statistics(user.id, db_session)

    assert stats["total_budgets"] == 3
    assert stats["total_limit"] == Decimal("350.00")
    assert stats["total_spent"] == Decimal("290.00")
    assert stats["status_counts"][BudgetStatus.NORMAL.value] == 1
    assert stats["status_counts"][BudgetStatus.WARNING.value] == 1
    assert stats["status_counts"][BudgetStatus.EXCEEDED.value] == 1
