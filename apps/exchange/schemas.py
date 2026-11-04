from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from core.constants.currency import Currency


class ExchangeRateErrorDetail(BaseModel):
    code: Literal["exchange_rate_unavailable", "exchange_rate_stale"]
    message: str
    from_currency: Currency
    to_currency: Currency
    updated_at: Optional[datetime] = None


class ExchangeRateErrorResponse(BaseModel):
    detail: ExchangeRateErrorDetail


EXCHANGE_RATE_FAILURE_RESPONSES = {
    503: {
        "model": ExchangeRateErrorResponse,
        "description": "A required exchange rate is missing or expired",
    },
}


class ExchangeRateResponse(BaseModel):
    """Response model for exchange rates. Read-only."""

    id: int = Field(..., description="Exchange rate ID")
    from_currency: Currency = Field(
        ..., description="Source currency (GBP, USD, or EUR)"
    )
    to_currency: Currency = Field(
        ..., description="Target currency (GBP, USD, or EUR)"
    )
    rate: Decimal = Field(..., description="Exchange rate")
    created_at: datetime = Field(
        ..., description="Exchange rate creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description=(
            "Last successful provider refresh in UTC, including unchanged "
            "quotes; not the provider's quote date"
        ),
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "from_currency": "GBP",
                "to_currency": "USD",
                "rate": "1.33285",
                "created_at": "2026-05-16T12:00:00Z",
                "updated_at": "2026-05-16T12:00:00Z",
            }
        }
