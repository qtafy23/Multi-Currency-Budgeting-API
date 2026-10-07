from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from core.constants.currency import Currency


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
        None, description="Exchange rate last update timestamp"
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
