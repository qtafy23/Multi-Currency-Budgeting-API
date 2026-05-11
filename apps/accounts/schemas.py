"""
Pydantic schemas for user authentication and data validation.
Provides extensible schemas for registration, login, and token responses.
"""
from typing import Optional

from pydantic import BaseModel, Field
from core.constants.currency import Currency


class AccountCreate(BaseModel):
    """Schema for account creation."""
    name: str = Field(..., description="Account name")
    currency: Currency = Field(default=Currency.USD, description="Currency code (e.g. USD, EUR)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Checking Account",
                "currency": "USD"
            }
        }


class AccountUpdate(BaseModel):
    """Schema for updating an existing account."""
    name: Optional[str] = Field(None, description="Updated account name")
    currency: Optional[Currency] = Field(None, description="Updated currency code")
    is_active: Optional[bool] = Field(None, description="Whether the account should remain active")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Savings",
                "currency": "EUR",
                "is_active": True
            }
        }


class AccountResponse(BaseModel):
    """Schema for account response."""
    id: int = Field(..., description="Account ID")
    user_id: int = Field(..., description="ID of the user who owns the account")
    name: str = Field(..., description="Account name")
    balance: float = Field(..., description="Current account balance")
    currency: Currency = Field(..., description="Currency code (e.g. USD, EUR)")
    is_active: bool = Field(..., description="Whether the account is active")

    class Config:
        model_config = {
            "from_attributes": True
        }
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1,
                "name": "My Checking Account",
                "balance": 1000.00,
                "currency": "USD",
                "is_active": True
            }
        }
