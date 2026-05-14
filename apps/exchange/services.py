from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.exchange.models import ExchangeRate
from core.constants.currency import Currency


class ExchangeRateService:
    """Service layer for exchange rate operations."""

    @staticmethod
    def create_rate(db: Session, payload: "ExchangeRateCreate") -> ExchangeRate:
        if payload.from_currency == payload.to_currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_currency and to_currency must differ"
            )

        rate_value = Decimal(str(payload.rate))
        if rate_value <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exchange rate must be greater than zero"
            )

        exchange_rate = ExchangeRate(
            from_currency=payload.from_currency,
            to_currency=payload.to_currency,
            rate=rate_value
        )

        try:
            db.add(exchange_rate)
            db.commit()
            db.refresh(exchange_rate)
            return exchange_rate
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Exchange rate pair already exists"
            )

    @staticmethod
    def get_rate(db: Session, from_currency: Currency, to_currency: Currency) -> ExchangeRate:
        rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency
        ).first()
        if not rate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Exchange rate from {from_currency} to {to_currency} not found"
            )
        return rate

    @staticmethod
    def get_rate_by_id(db: Session, rate_id: int) -> ExchangeRate:
        rate = db.query(ExchangeRate).filter(ExchangeRate.id == rate_id).first()
        if not rate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exchange rate not found"
            )
        return rate

    @staticmethod
    def update_rate(db: Session, rate_id: int, payload: "ExchangeRateUpdate") -> ExchangeRate:
        exchange_rate = ExchangeRateService.get_rate_by_id(db, rate_id)

        if payload.rate is not None:
            rate_value = Decimal(str(payload.rate))
            if rate_value <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Exchange rate must be greater than zero"
                )
            exchange_rate.rate = rate_value

        db.commit()
        db.refresh(exchange_rate)
        return exchange_rate

    @staticmethod
    def convert_amount(
        db: Session,
        from_currency: Currency,
        to_currency: Currency,
        amount: Decimal
    ) -> Decimal:
        source_currency = Currency(from_currency) if not isinstance(from_currency, Currency) else from_currency
        target_currency = Currency(to_currency) if not isinstance(to_currency, Currency) else to_currency
        amount_value = Decimal(str(amount))

        if source_currency == target_currency:
            return amount_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        exchange_rate = ExchangeRateService.get_rate(db, source_currency, target_currency)
        converted = (amount_value * Decimal(str(exchange_rate.rate))).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
        return converted
