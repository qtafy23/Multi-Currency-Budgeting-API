"""
Pydantic schemas for user authentication and data validation.
Provides extensible schemas for registration, login, and token responses.
"""
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from core.constants.currency import Currency
from apps.transactions.schemas import TransactionResponse


class AccountCreate(BaseModel):
    """Schema for account creation."""

    name: str = Field(..., description="Account name")
    currency: Currency = Field(
        default=Currency.USD, description="Currency code (e.g. USD, EUR)"
    )

    class Config:
        json_schema_extra = {
            "example": {"name": "My Checking Account", "currency": "USD"}
        }


class AccountUpdate(BaseModel):
    """Schema for updating an existing account."""

    name: Optional[str] = Field(
        None, description="Updated account name"
    )
    is_active: Optional[bool] = Field(
        None, description="Whether the account is active"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Savings",
                "is_active": True,
            }
        }


class AccountResponse(BaseModel):
    """Schema for account response."""
    
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ..., description="Account ID"
    )
    user_id: int = Field(
        ..., description="ID of the user who owns the account"
    )
    name: str = Field(
        ..., description="Account name"
    )
    currency: Currency = Field(
        ..., description="Currency code (e.g. USD, EUR)"
    )
    balance: Decimal = Field(
        ..., description="Current account balance"
    )
    is_active: bool = Field(
        ..., description="Whether the account is active"
    )


class AccountCurrencyConversionRequest(BaseModel):
    """Request to convert the entire account balance."""

    target_currency: Currency = Field(
        ...,
        description="Currency to convert the account balance into",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_currency": "EUR",
            }
        }


class AccountCurrencyConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account: AccountResponse
    transaction: Optional[TransactionResponse] = None
    event_id: Optional[int] = None
    converted: bool

