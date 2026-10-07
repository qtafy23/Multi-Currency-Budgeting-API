from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.exchange.models import ExchangeRate
from apps.exchange.schemas import ExchangeRateResponse
from apps.exchange.services import ExchangeRateService
from apps.users.models import User
from apps.users.routes import get_current_user, get_db

router = APIRouter(prefix="/exchange-rates", tags=["Exchange Rates"])


@router.get("/", response_model=List[ExchangeRateResponse])
def list_exchange_rates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ExchangeRateResponse]:
    """List rates managed by Frankfurter and refreshed by scheduled tasks."""
    return (
        db.query(ExchangeRate).order_by(ExchangeRate.created_at.desc()).all()
    )


@router.get("/{rate_id}", response_model=ExchangeRateResponse)
def get_exchange_rate(
    rate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExchangeRateResponse:
    """Retrieve a system-managed exchange rate by ID."""
    return ExchangeRateService.get_rate_by_id(db, rate_id)
