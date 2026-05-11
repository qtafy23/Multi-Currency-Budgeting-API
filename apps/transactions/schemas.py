from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from pydantic import BaseModel, Field


class TransactionType(str, PyEnum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionCreate(BaseModel):
    account_id: int = Field(..., description="ID of the account to apply the transaction")
    type: TransactionType = Field(..., description="Transaction type: income or expense")
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    note: Optional[str] = Field(None, description="Optional transaction note")

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": 1,
                "type": "expense",
                "amount": 150.00,
                "note": "Grocery shopping"
            }
        }


class TransactionResponse(BaseModel):
    id: int = Field(..., description="Transaction ID")
    account_id: int = Field(..., description="ID of the account")
    type: TransactionType = Field(..., description="Transaction type")
    amount: Decimal = Field(..., description="Transaction amount")
    balance_after: Decimal = Field(..., description="Balance after the transaction")
    currency: str = Field(..., description="Account currency")
    note: Optional[str] = Field(None, description="Optional transaction note")
    created_at: datetime = Field(..., description="Transaction timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "account_id": 1,
                "type": "income",
                "amount": 500.00,
                "balance_after": 1500.00,
                "currency": "USD",
                "note": "Salary",
                "created_at": "2026-05-11T12:34:56Z"
            }
        }
