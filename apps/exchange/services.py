import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, Optional

import requests
from fastapi import HTTPException, status
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from apps.exchange.models import ExchangeRate
from core.config.settings import settings
from core.constants.currency import (
    EXCHANGE_BASE_CURRENCY,
    FRANKFURTER_RATES_URL,
    SUPPORTED_CURRENCIES,
    Currency,
)

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """
    Service layer for exchange rate operations.
    Rates are system-managed exclusively via Frankfurter API and Celery tasks.
    """

    @staticmethod
    def get_rate(
        db: Session, from_currency: Currency, to_currency: Currency
    ) -> ExchangeRate:
        """Retrieve a usable rate, or report an unavailable dependency."""
        rate = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.from_currency == from_currency,
                ExchangeRate.to_currency == to_currency,
            )
            .first()
        )
        if not rate:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "exchange_rate_unavailable",
                    "message": "Required exchange rate is unavailable",
                    "from_currency": from_currency.value,
                    "to_currency": to_currency.value,
                    "updated_at": None,
                }
            )
        updated_at = rate.updated_at
        if updated_at is not None:
            updated_at = (
                updated_at.replace(tzinfo=timezone.utc)
                if updated_at.tzinfo is None
                else updated_at.astimezone(timezone.utc)
            )
        expires_before = datetime.now(timezone.utc) - timedelta(
            hours=settings.exchange_rate_max_age_hours
        )
        if updated_at is None or updated_at <= expires_before:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "exchange_rate_stale",
                    "message": "Required exchange rate has expired",
                    "from_currency": from_currency.value,
                    "to_currency": to_currency.value,
                    "updated_at": (
                        updated_at.isoformat() if updated_at else None
                    ),
                },
            )
        return rate

    @staticmethod
    def get_rate_by_id(db: Session, rate_id: int) -> ExchangeRate:
        """Retrieve exchange rate by ID."""
        rate = (
            db.query(ExchangeRate).filter(ExchangeRate.id == rate_id).first()
        )
        if not rate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exchange rate not found",
            )
        return rate

    @staticmethod
    def convert_amount(
        db: Session,
        from_currency: Currency,
        to_currency: Currency,
        amount: Decimal,
    ) -> Decimal:
        """
        Convert amount from one currency to another
        using latest exchange rates.
        """
        source_currency = (
            Currency(from_currency)
            if not isinstance(from_currency, Currency)
            else from_currency
        )
        target_currency = (
            Currency(to_currency)
            if not isinstance(to_currency, Currency)
            else to_currency
        )
        amount_value = Decimal(str(amount))

        if source_currency == target_currency:
            return amount_value.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        exchange_rate = ExchangeRateService.get_rate(
            db, source_currency, target_currency
        )
        converted = (amount_value * Decimal(str(exchange_rate.rate))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return converted

    @staticmethod
    def fetch_from_frankfurter(
        base_currency: Currency,
        target_currencies: list[Currency],
        timeout_seconds: int = 10,
    ) -> Optional[Dict[str, Decimal]]:
        """
        Fetch exchange rates from Frankfurter API.

        Returns a dict mapping target
        currency code -> rate value, or None on error.
        """
        currency_codes = ",".join(curr.value for curr in target_currencies)
        params = {
            "base": base_currency.value,
            "quotes": currency_codes,
        }

        logger.debug(
            "Frankfurter request: endpoint=%s params=%s",
            FRANKFURTER_RATES_URL,
            params,
        )
        try:
            response = requests.get(
                FRANKFURTER_RATES_URL, params=params, timeout=timeout_seconds
            )
            response.raise_for_status()
            payload = response.json()
        except (RequestException, ValueError) as exc:
            logger.error("Frankfurter request failed (%s)", type(exc).__name__)
            return None

        try:
            if isinstance(payload, dict):
                rates_payload = payload.get("rates")
                if not isinstance(rates_payload, dict):
                    logger.error(
                        "Frankfurter returned an unexpected response format"
                    )
                    return None

                allowed_codes = {
                    currency.value for currency in target_currencies
                }
                return {
                    str(code).upper(): Decimal(str(value))
                    for code, value in rates_payload.items()
                    if str(code).upper() in allowed_codes
                }

            if isinstance(payload, list):
                rates = {
                    str(item["quote"]).upper(): Decimal(str(item["rate"]))
                    for item in payload
                    if isinstance(item, dict)
                    and str(item.get("base", "")).upper()
                    == base_currency.value
                    and str(item.get("quote", "")).upper()
                    in {currency.value for currency in target_currencies}
                }
                return rates

            logger.error("Frankfurter returned an unexpected response format")
            return None
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            logger.error(
                "Failed to parse Frankfurter response (%s)", type(exc).__name__
            )
            return None

    @staticmethod
    def refresh_rates_from_frankfurter(
        db: Session, timeout_seconds: int = 10
    ) -> int:
        """
        Refresh all required exchange rates
        from Frankfurter using EUR as the base.

        Updates existing records and creates missing ones.
        Returns the total number of rates updated/created.
        """
        supported_currencies = SUPPORTED_CURRENCIES
        base_currency = EXCHANGE_BASE_CURRENCY
        target_currencies = [
            currency
            for currency in supported_currencies
            if currency != base_currency
        ]
        eur_rates = ExchangeRateService.fetch_from_frankfurter(
            base_currency, target_currencies, timeout_seconds
        )
        if eur_rates is None:
            raise RuntimeError("Frankfurter rate fetch failed")

        # Validate a complete snapshot before changing any cached pairs.
        if any(
            currency.value not in eur_rates for currency in target_currencies
        ):
            raise RuntimeError(
                "Frankfurter response is missing required quotes"
            )
        if any(
            not value.is_finite() or value <= 0
            for value in eur_rates.values()
        ):
            raise RuntimeError("Frankfurter response contains an invalid rate")
        normalized_rates = {
            base_currency: Decimal("1"),
            **{Currency(code): rate for code, rate in eur_rates.items()},
        }
        pairs = []
        for source in supported_currencies:
            for target in supported_currencies:
                if source == target:
                    continue
                value = (normalized_rates[target] / normalized_rates[source])
                canonical_rate = value.quantize(
                    Decimal("0.00000001"), rounding=ROUND_HALF_UP
                )
                if not 0 < canonical_rate < Decimal("10000000000"):
                    raise RuntimeError("Frankfurter rate is out of range")
                pairs.append((source, target, canonical_rate))
        refreshed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        total_count = 0
        updated_count = 0
        created_count = 0

        for from_currency, to_currency, canonical_rate in pairs:
            existing_rate = (
                db.query(ExchangeRate)
                .filter(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                )
                .first()
            )
            if existing_rate:
                existing_rate.rate = canonical_rate
                existing_rate.updated_at = refreshed_at
                updated_count += 1
            else:
                db.add(ExchangeRate(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=canonical_rate,
                    updated_at=refreshed_at,
                ))
                created_count += 1

        db.commit()
        total_count = updated_count + created_count
        logger.info(
            "Exchange rate refresh complete using one "
            "EUR-based request: %d updated, %d created",
            updated_count,
            created_count,
        )
        return total_count
