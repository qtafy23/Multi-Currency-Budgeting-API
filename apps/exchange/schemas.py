from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, validator

from core.constants.currency import Currency


class ExchangeRateCreate(BaseModel):
    from_currency: Currency = Field(..., description="Source currency code")
    to_currency: Currency = Field(..., description="Target currency code")
    rate: Decimal = Field(..., gt=0, description="Exchange rate from source to target")

    @validator("to_currency")
    def different_currency_pair(cls, value, values):
        if values.get("from_currency") == value:
            raise ValueError("from_currency and to_currency must differ")
        return value

    class Config:
        json_schema_extra = {
            "example": {
                "from_currency": "EUR",
                "to_currency": "USD",
                "rate": "1.0845"
            }
        }


class ExchangeRateUpdate(BaseModel):
    rate: Optional[Decimal] = Field(None, gt=0, description="Updated exchange rate")

    class Config:
        json_schema_extra = {
            "example": {
                "rate": "1.0845"
            }
        }


class ExchangeRateResponse(BaseModel):
    id: int = Field(..., description="Exchange rate ID")
    from_currency: Currency = Field(..., description="Source currency code")
    to_currency: Currency = Field(..., description="Target currency code")
    rate: Decimal = Field(..., description="Exchange rate")
    created_at: datetime = Field(..., description="Exchange rate creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Exchange rate last update timestamp")

    class Config:
        from_attributes = True
