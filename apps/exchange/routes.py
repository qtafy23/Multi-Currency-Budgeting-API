from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from apps.exchange.models import ExchangeRate
from apps.exchange.schemas import (
    ExchangeRateCreate,
    ExchangeRateResponse,
    ExchangeRateUpdate
)
from apps.exchange.services import ExchangeRateService
from apps.users.models.users import User
from apps.users.routes import get_current_user, get_db

router = APIRouter(prefix="/exchange-rates", tags=["Exchange Rates"])


@router.post("/", response_model=ExchangeRateResponse, status_code=status.HTTP_201_CREATED)
def create_exchange_rate(
    payload: ExchangeRateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ExchangeRateResponse:
    """Create a new currency exchange rate."""
    exchange_rate = ExchangeRateService.create_rate(db, payload)
    return exchange_rate


@router.get("/", response_model=List[ExchangeRateResponse])
def list_exchange_rates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[ExchangeRateResponse]:
    """List all configured exchange rates."""
    return db.query(ExchangeRate).order_by(ExchangeRate.created_at.desc()).all()


@router.get("/{rate_id}", response_model=ExchangeRateResponse)
def get_exchange_rate(
    rate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ExchangeRateResponse:
    """Retrieve a single exchange rate by ID."""
    return ExchangeRateService.get_rate_by_id(db, rate_id)


@router.patch("/{rate_id}", response_model=ExchangeRateResponse)
def update_exchange_rate(
    rate_id: int,
    payload: ExchangeRateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ExchangeRateResponse:
    """Update an existing exchange rate."""
    return ExchangeRateService.update_rate(db, rate_id, payload)


@router.delete("/{rate_id}")
def delete_exchange_rate(
    rate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Delete an exchange rate."""
    exchange_rate = ExchangeRateService.get_rate_by_id(db, rate_id)
    db.delete(exchange_rate)
    db.commit()
    return {"detail": "Exchange rate deleted successfully"}
