from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, condecimal

from core.constants.budgets import BudgetPeriod, BudgetStatus
from core.constants.currency import Currency


class BudgetCreate(BaseModel):
    category: str = Field(
        ..., description="Budget category for tracked spending"
    )
    limit: condecimal(gt=0, max_digits=12, decimal_places=2) = Field(
        ..., description="Spending limit for the budget"
    )
    currency: Currency = Field(
        default=Currency.EUR,
        description="Currency used by this budget",
    )
    period: BudgetPeriod = Field(
        default=BudgetPeriod.MONTHLY, description="Budget period"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "category": "groceries",
                "limit": 500.00,
                "currency": "EUR",
                "period": "monthly",
            }
        }


class BudgetUpdate(BaseModel):
    limit: Optional[condecimal(gt=0, max_digits=12, decimal_places=2)] = Field(
        None, description="New spending limit for the budget"
    )
    currency: Optional[Currency] = Field(
        None, description="New currency for the budget limit"
    )

    class Config:
        json_schema_extra = {"example": {"limit": 600.00, "currency": "USD"}}


class BudgetResponse(BaseModel):
    id: int = Field(..., description="Budget ID")
    user_id: int = Field(..., description="User ID")
    category: str = Field(..., description="Budget category")
    limit: Decimal = Field(..., description="Spending limit")
    spent_amount: Decimal = Field(..., description="Amount already spent")
    period: BudgetPeriod = Field(..., description="Budget period")
    currency: Currency = Field(..., description="Budget currency")
    status: BudgetStatus = Field(..., description="Current budget status")
    usage_percentage: float = Field(..., description="Budget usage percentage")
    remaining_amount: Decimal = Field(
        ..., description="Remaining budget amount"
    )
    created_at: datetime = Field(..., description="Budget creation timestamp")
    updated_at: Optional[datetime] = Field(
        None, description="Budget update timestamp"
    )

    class Config:
        model_config = {"from_attributes": True}


class BudgetStatusCounts(BaseModel):
    normal: int = Field(0, description="Number of budgets in normal status")
    warning: int = Field(0, description="Number of budgets in warning status")
    exceeded: int = Field(
        0, description="Number of budgets in exceeded status"
    )


class BudgetStatisticsResponse(BaseModel):
    total_budgets: int = Field(..., description="Total number of budgets")
    currency: Currency = Field(..., description="Currency for totals")
    total_limit: Decimal = Field(
        ..., description="Sum of all budget limits converted to EUR"
    )
    total_spent: Decimal = Field(
        ...,
        description=(
            "Expenses covered by at least one of the user's budgets in its "
            "current UTC calendar period, counted once and converted "
            "directly from transaction currencies to EUR. Excludes "
            "unbudgeted expenses; zero when there are no budgets."
        ),
    )
    total_remaining: Decimal = Field(
        ...,
        description=(
            "Sum of remaining allowances for each budget, converted to EUR. "
            "Overlapping budgets are independent, so this need not equal "
            "total_limit minus total_spent."
        ),
    )
    status_counts: BudgetStatusCounts = Field(
        ..., description="Budget counts by status"
    )


class BudgetCheckRequest(BaseModel):
    category: str = Field(
        ..., description="Category to validate against budgets"
    )
    amount: Decimal = Field(
        ..., gt=0, description="Expense amount to validate"
    )
    currency: Currency = Field(
        default=Currency.EUR,
        description="Currency of the proposed expense amount",
    )
    period: Optional[BudgetPeriod] = Field(
        None, description="Optional budget period to check"
    )


class BudgetCheckResponse(BaseModel):
    category: str = Field(..., description="Budget category")
    period: BudgetPeriod = Field(..., description="Budget period")
    limit: Decimal = Field(..., description="Budget limit")
    currency: Currency = Field(..., description="Budget currency")
    spent_amount: Decimal = Field(..., description="Budget spent amount")
    remaining_amount: Decimal = Field(
        ..., description="Remaining budget amount"
    )
    usage_percentage: float = Field(..., description="Budget usage percentage")
    status: BudgetStatus = Field(..., description="Current budget status")
    warning: Optional[str] = Field(
        None, description="Overspending warning message"
    )
