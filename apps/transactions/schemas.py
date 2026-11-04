from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from core.constants.currency import Currency
from core.constants.transaction import TransactionType


class TransactionCreate(BaseModel):
    account_id: int = Field(
        ..., description="ID of the account to apply the transaction"
    )
    type: TransactionType = Field(
        ..., description="Transaction type: income or expense"
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Transaction amount",
    )
    currency: Currency = Field(
        ..., description="Currency code for the incoming transaction"
    )
    category: Optional[str] = Field(
        None, description="Optional budget category for expense tracking"
    )
    note: Optional[str] = Field(None, description="Optional transaction note")

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": 1,
                "type": "expense",
                "amount": 150.00,
                "currency": "USD",
                "note": "Grocery shopping",
            }
        }


class TransactionResponse(BaseModel):
    id: int = Field(..., description="Transaction ID")
    account_id: int = Field(..., description="ID of the account")
    type: TransactionType = Field(..., description="Transaction type")
    original_amount: Optional[Decimal] = Field(
        None,
        description="Original transaction amount before currency conversion",
    )
    converted_amount: Optional[Decimal] = Field(
        None, description="Transaction amount converted into account currency"
    )
    original_currency: Optional[Currency] = Field(
        None, description="Original transaction currency"
    )
    account_currency: Optional[Currency] = Field(
        None, description="Account currency"
    )
    exchange_rate: Optional[Decimal] = Field(
        None, description="Exchange rate used for currency conversion"
    )
    amount: Decimal = Field(
        ..., description="Amount applied to the account balance"
    )
    balance_after: Decimal = Field(
        ..., description="Balance after the transaction"
    )
    currency: Currency = Field(..., description="Account currency")
    category: Optional[str] = Field(
        None, description="Budget category for the transaction"
    )
    note: Optional[str] = Field(None, description="Optional transaction note")
    created_at: datetime = Field(..., description="Transaction timestamp")
    budget_warning: Optional[str] = Field(
        None, description="Optional warning when a category budget is exceeded"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "account_id": 1,
                "type": "income",
                "original_amount": 500.00,
                "converted_amount": 500.00,
                "original_currency": "USD",
                "account_currency": "USD",
                "amount": 500.00,
                "balance_after": 1500.00,
                "currency": "USD",
                "category": "groceries",
                "note": "Salary",
                "budget_warning": (
                    "Budget limit exceeded for category 'groceries'",
                ),
                "created_at": "2026-05-11T12:34:56Z",
            }
        }
