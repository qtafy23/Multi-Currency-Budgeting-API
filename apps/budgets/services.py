from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from apps.accounts.models import Account
from apps.budgets.models import Budget
from apps.budgets.schemas import BudgetCreate, BudgetUpdate
from apps.exchange.services import ExchangeRateService
from apps.transactions.models import Transaction
from core.constants.budgets import BudgetPeriod, BudgetStatus
from core.constants.currency import EXCHANGE_BASE_CURRENCY, Currency
from core.constants.transaction import TransactionType


class BudgetService:
    """Service layer for budget operations."""

    @staticmethod
    def normalize_category(category: str) -> str:
        return category.strip().lower()

    @staticmethod
    def _period_window(
        period: BudgetPeriod, as_of: Optional[datetime] = None
    ) -> tuple[datetime, datetime]:
        current = as_of or datetime.now(timezone.utc)
        if current.tzinfo is not None:
            current = current.astimezone(timezone.utc).replace(tzinfo=None)

        if period == BudgetPeriod.WEEKLY:
            week_start = current - timedelta(days=current.weekday())
            period_start = week_start.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return period_start, period_start + timedelta(days=7)

        period_start = current.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if period_start.month == 12:
            period_end = period_start.replace(
                year=period_start.year + 1, month=1
            )
        else:
            period_end = period_start.replace(month=period_start.month + 1)
        return period_start, period_end

    @staticmethod
    def get_budget_spent_amount(
        user_id: int,
        budget: Budget,
        db: Session,
        as_of: Optional[datetime] = None,
    ) -> Decimal:
        period_start, period_end = BudgetService._period_window(
            budget.period, as_of
        )
        normalized_category = BudgetService.normalize_category(
            budget.category
        )
        totals_by_currency = (
            db.query(
                Transaction.currency,
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .join(Account, Account.id == Transaction.account_id)
            .filter(
                Account.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                func.lower(func.trim(Transaction.category))
                == normalized_category,
                Transaction.created_at >= period_start,
                Transaction.created_at < period_end,
            )
            .group_by(Transaction.currency)
            .all()
        )
        total_spent = Decimal("0")
        for transaction_currency, amount in totals_by_currency:
            total_spent += ExchangeRateService.convert_amount(
                db,
                Currency(transaction_currency),
                Currency(budget.currency),
                Decimal(str(amount)),
            )
        return total_spent

    @staticmethod
    def get_budget_summary(
        user_id: int,
        budget: Budget,
        db: Session,
        as_of: Optional[datetime] = None,
    ) -> dict:
        spent_amount = BudgetService.get_budget_spent_amount(
            user_id, budget, db, as_of
        )
        remaining_amount = max(budget.limit - spent_amount, Decimal("0"))
        usage_percentage = (
            float(
                min(
                    Decimal("100"),
                    spent_amount / budget.limit * Decimal("100"),
                )
            )
            if budget.limit
            else 0.0
        )
        if spent_amount >= budget.limit:
            budget_status = BudgetStatus.EXCEEDED
        elif spent_amount >= budget.limit * Decimal("0.8"):
            budget_status = BudgetStatus.WARNING
        else:
            budget_status = BudgetStatus.NORMAL

        return {
            "spent_amount": spent_amount,
            "remaining_amount": remaining_amount,
            "usage_percentage": usage_percentage,
            "status": budget_status,
        }

    @staticmethod
    def serialize_budget(
        user_id: int,
        budget: Budget,
        db: Session,
        as_of: Optional[datetime] = None,
    ) -> dict:
        return {
            "id": budget.id,
            "user_id": budget.user_id,
            "category": budget.category,
            "limit": budget.limit,
            "currency": Currency(budget.currency),
            "period": budget.period,
            "created_at": budget.created_at,
            "updated_at": budget.updated_at,
            **BudgetService.get_budget_summary(user_id, budget, db, as_of),
        }

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
            currency=payload.currency.value,
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
        if payload.currency is not None:
            budget.currency = payload.currency.value

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
    def _get_total_budgeted_spending(
        user_id: int, db: Session, as_of: datetime
    ) -> Decimal:
        """Sum each expense covered by any current user budget once, in EUR."""
        windows = []
        for period in BudgetPeriod:
            start, end = BudgetService._period_window(period, as_of)
            windows.append(and_(
                Budget.period == period,
                Transaction.created_at >= start,
                Transaction.created_at < end,
            ))
        matching_budget = (
            db.query(Budget.id)
            .filter(
                Budget.user_id == user_id,
                func.lower(func.trim(Budget.category))
                == func.lower(func.trim(Transaction.category)),
                or_(*windows),
            )
            .exists()
        )
        # EXISTS avoids multiplying a transaction when several budgets match.
        totals_by_currency = (
            db.query(Transaction.currency, func.sum(Transaction.amount))
            .join(Account, Account.id == Transaction.account_id)
            .filter(
                Account.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                matching_budget,
            )
            .group_by(Transaction.currency)
            .all()
        )
        return sum(
            (
                ExchangeRateService.convert_amount(
                    db, Currency(currency), EXCHANGE_BASE_CURRENCY,
                    Decimal(str(amount)),
                )
                for currency, amount in totals_by_currency
            ),
            Decimal("0"),
        )


    @staticmethod
    def get_budget_statistics(
        user_id: int, db: Session, as_of: Optional[datetime] = None
    ) -> dict:
        as_of = as_of or datetime.now(timezone.utc)
        budgets = BudgetService.get_user_budgets(user_id, db)
        total_limit = sum(
            (
                ExchangeRateService.convert_amount(
                    db,
                    Currency(budget.currency),
                    EXCHANGE_BASE_CURRENCY,
                    budget.limit or Decimal("0"),
                )
                for budget in budgets
            ),
            Decimal("0"),
        )
        summaries = [
            BudgetService.get_budget_summary(user_id, budget, db, as_of)
            for budget in budgets
        ]
        total_spent = (
            BudgetService._get_total_budgeted_spending(user_id, db, as_of)
            if budgets else Decimal("0")
        )
        total_remaining = sum(
            (
                ExchangeRateService.convert_amount(
                    db,
                    Currency(budget.currency),
                    EXCHANGE_BASE_CURRENCY,
                    summary["remaining_amount"],
                )
                for budget, summary in zip(budgets, summaries)
            ),
            Decimal("0"),
        )
        status_counts = {
            BudgetStatus.NORMAL.value: 0,
            BudgetStatus.WARNING.value: 0,
            BudgetStatus.EXCEEDED.value: 0,
        }
        for summary in summaries:
            status_counts[summary["status"].value] += 1

        return {
            "total_budgets": len(budgets),
            "currency": EXCHANGE_BASE_CURRENCY,
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
        currency: Currency = Currency.EUR,
    ) -> List[dict]:
        budgets = BudgetService.get_category_budgets(
            user_id, category, db, period
        )
        if not budgets:
            return []

        response = []
        for budget in budgets:
            summary = BudgetService.get_budget_summary(
                user_id, budget, db
            )
            converted_amount = ExchangeRateService.convert_amount(
                db,
                currency,
                Currency(budget.currency),
                amount,
            )
            projected_spent = summary["spent_amount"] + converted_amount
            warning = None
            if projected_spent >= budget.limit:
                warning = "Budget limit exceeded"
            elif projected_spent >= budget.limit * Decimal("0.8"):
                warning = "Budget usage has reached 80% of the limit"

            response.append({
                "category": budget.category,
                "period": budget.period,
                "limit": budget.limit,
                "currency": Currency(budget.currency),
                **summary,
                "warning": warning,
            })
        return response

    @staticmethod
    def get_expense_budget_warning(
        user_id: int,
        category: str,
        amount: Decimal,
        currency: Currency,
        db: Session,
    ) -> Optional[str]:
        budgets = BudgetService.get_category_budgets(user_id, category, db)
        if not budgets:
            return None

        warning: Optional[str] = None
        for budget in budgets:
            summary = BudgetService.get_budget_summary(
                user_id, budget, db
            )
            converted_amount = ExchangeRateService.convert_amount(
                db, currency, Currency(budget.currency), amount
            )
            projected_spent = summary["spent_amount"] + converted_amount
            if projected_spent >= budget.limit:
                warning = f"Budget limit exceeded for category '{category}'"
            elif projected_spent >= budget.limit * Decimal("0.8"):
                warning = (
                    warning
                    or f"Budget usage reached 80% for category '{category}'"
                )

        return warning
