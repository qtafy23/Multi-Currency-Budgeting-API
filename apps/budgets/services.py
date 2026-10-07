from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from apps.budgets.models import Budget
from apps.budgets.schemas import BudgetCreate, BudgetUpdate
from core.constants.budgets import BudgetPeriod, BudgetStatus


class BudgetService:
    """Service layer for budget operations."""

    @staticmethod
    def normalize_category(category: str) -> str:
        return category.strip().lower()

    @staticmethod
    def create_budget(
        user_id: int, payload: BudgetCreate, db: Session
    ) -> Budget:
        category = BudgetService.normalize_category(payload.category)
        existing = (
            db.query(Budget)
            .filter(
                Budget.user_id == user_id,
                Budget.category == category,
                Budget.period == payload.period,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A budget already exists for this category and period",
            )

        budget = Budget(
            user_id=user_id,
            category=category,
            limit=payload.limit,
            spent_amount=Decimal("0"),
            period=payload.period,
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        return budget

    @staticmethod
    def get_budget_by_id(user_id: int, budget_id: int, db: Session) -> Budget:
        budget = (
            db.query(Budget)
            .filter(Budget.id == budget_id, Budget.user_id == user_id)
            .first()
        )
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found",
            )
        return budget

    @staticmethod
    def get_user_budgets(user_id: int, db: Session) -> List[Budget]:
        return (
            db.query(Budget)
            .filter(Budget.user_id == user_id)
            .order_by(Budget.category, Budget.period)
            .all()
        )

    @staticmethod
    def update_budget(
        user_id: int, budget_id: int, payload: BudgetUpdate, db: Session
    ) -> Budget:
        budget = BudgetService.get_budget_by_id(user_id, budget_id, db)

        if payload.limit is not None:
            budget.limit = payload.limit

        db.commit()
        db.refresh(budget)
        return budget

    @staticmethod
    def delete_budget(user_id: int, budget_id: int, db: Session) -> None:
        budget = BudgetService.get_budget_by_id(user_id, budget_id, db)
        db.delete(budget)
        db.commit()

    @staticmethod
    def get_category_budgets(
        user_id: int,
        category: str,
        db: Session,
        period: Optional[BudgetPeriod] = None,
    ) -> List[Budget]:
        category_key = BudgetService.normalize_category(category)
        query = db.query(Budget).filter(
            Budget.user_id == user_id, Budget.category == category_key
        )
        if period is not None:
            query = query.filter(Budget.period == period)
        return query.all()

    @staticmethod
    def get_budget_statistics(user_id: int, db: Session) -> dict:
        budgets = BudgetService.get_user_budgets(user_id, db)
        total_limit = sum((budget.limit or Decimal("0")) for budget in budgets)
        total_spent = sum(
            (budget.spent_amount or Decimal("0")) for budget in budgets
        )
        total_remaining = sum(
            (budget.remaining_amount or Decimal("0")) for budget in budgets
        )
        status_counts = {
            BudgetStatus.NORMAL.value: 0,
            BudgetStatus.WARNING.value: 0,
            BudgetStatus.EXCEEDED.value: 0,
        }
        for budget in budgets:
            status_counts[budget.status.value] += 1

        return {
            "total_budgets": len(budgets),
            "total_limit": total_limit,
            "total_spent": total_spent,
            "total_remaining": total_remaining,
            "status_counts": status_counts,
        }

    @staticmethod
    def check_budget_usage(
        user_id: int,
        category: str,
        amount: Decimal,
        db: Session,
        period: Optional[BudgetPeriod] = None,
    ) -> List[dict]:
        budgets = BudgetService.get_category_budgets(
            user_id, category, db, period
        )
        if not budgets:
            return []

        response = []
        for budget in budgets:
            projected_spent = (budget.spent_amount or Decimal("0")) + amount
            warning = None
            if projected_spent >= budget.limit:
                warning = "Budget limit exceeded"
            elif projected_spent >= budget.limit * Decimal("0.8"):
                warning = "Budget usage has reached 80% of the limit"

            response.append(
                {
                    "category": budget.category,
                    "period": budget.period,
                    "limit": budget.limit,
                    "spent_amount": budget.spent_amount,
                    "remaining_amount": budget.remaining_amount,
                    "usage_percentage": budget.usage_percentage,
                    "status": budget.status,
                    "warning": warning,
                }
            )
        return response

    @staticmethod
    def update_budget_spent_amount(
        user_id: int, category: str, amount: Decimal, db: Session
    ) -> Optional[str]:
        budgets = BudgetService.get_category_budgets(user_id, category, db)
        if not budgets:
            return None

        warning: Optional[str] = None
        for budget in budgets:
            budget.spent_amount = (
                budget.spent_amount or Decimal("0")
            ) + amount
            if budget.spent_amount >= budget.limit:
                warning = f"Budget limit exceeded for category '{category}'"
            elif budget.spent_amount >= budget.limit * Decimal("0.8"):
                warning = (
                    warning
                    or f"Budget usage reached 80% for category '{category}'"
                )

        db.flush()
        return warning
