import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Optional

import requests
from fastapi import HTTPException, status
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from apps.exchange.models import ExchangeRate
from core.constants.currency import (
    Currency,
    EXCHANGE_BASE_CURRENCY,
    FRANKFURTER_RATES_URL,
    SUPPORTED_CURRENCIES,
)

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """
    Service layer for exchange rate operations.
    Rates are system-managed exclusively via Frankfurter API and Celery tasks.
    """

    @staticmethod
    def get_rate(db: Session, from_currency: Currency, to_currency: Currency) -> ExchangeRate:
        """Retrieve exchange rate from database."""
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
        """Retrieve exchange rate by ID."""
        rate = db.query(ExchangeRate).filter(ExchangeRate.id == rate_id).first()
        if not rate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exchange rate not found"
            )
        return rate

    @staticmethod
    def convert_amount(
        db: Session,
        from_currency: Currency,
        to_currency: Currency,
        amount: Decimal
    ) -> Decimal:
        """Convert amount from one currency to another using latest exchange rates."""
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

    @staticmethod
    def fetch_from_frankfurter(
        base_currency: Currency,
        target_currencies: list[Currency],
        timeout_seconds: int = 10
    ) -> Optional[Dict[str, Decimal]]:
        """
        Fetch exchange rates from Frankfurter API.
        
        Returns a dict mapping target currency code -> rate value, or None on error.
        """
        currency_codes = ",".join(curr.value for curr in target_currencies)
        params = {
            "from": base_currency.value,
            "to": currency_codes,
        }

        logger.debug("Frankfurter request: endpoint=%s params=%s", FRANKFURTER_RATES_URL, params)
        try:
            response = requests.get(
                FRANKFURTER_RATES_URL,
                params=params,
                timeout=timeout_seconds
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
                    logger.error("Frankfurter returned an unexpected response format")
                    return None

                allowed_codes = {currency.value for currency in target_currencies}
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
                    and str(item.get("base", "")).upper() == base_currency.value
                    and str(item.get("quote", "")).upper() in {currency.value for currency in target_currencies}
                }
                return rates

            logger.error("Frankfurter returned an unexpected response format")
            return None
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            logger.error("Failed to parse Frankfurter response (%s)", type(exc).__name__)
            return None

    @staticmethod
    def refresh_rates_from_frankfurter(
        db: Session,
        timeout_seconds: int = 10
    ) -> int:
        """
        Refresh all required exchange rates from Frankfurter using EUR as the base.
        
        Updates existing records and creates missing ones.
        Returns the total number of rates updated/created.
        """
        supported_currencies = SUPPORTED_CURRENCIES
        base_currency = EXCHANGE_BASE_CURRENCY
        target_currencies = [currency for currency in supported_currencies if currency != base_currency]
        eur_rates = ExchangeRateService.fetch_from_frankfurter(
            base_currency,
            target_currencies,
            timeout_seconds
        )
        if eur_rates is None:
            raise RuntimeError("Frankfurter rate fetch failed")

        normalized_rates = {Currency(code): rate for code, rate in eur_rates.items()}
        total_count = 0
        updated_count = 0
        created_count = 0

        for from_currency in supported_currencies:
            for to_currency in supported_currencies:
                if from_currency == to_currency:
                    continue

                if from_currency == base_currency:
                    rate_value = normalized_rates.get(to_currency)
                elif to_currency == base_currency:
                    base_rate = normalized_rates.get(from_currency)
                    rate_value = Decimal("1") / base_rate if base_rate else None
                else:
                    base_rate = normalized_rates.get(from_currency)
                    target_rate = normalized_rates.get(to_currency)
                    rate_value = target_rate / base_rate if base_rate else None

                if rate_value is None:
                    logger.warning(
                        "Frankfurter response is missing the EUR-based quote needed for %s -> %s",
                        from_currency.value,
                        to_currency.value,
                    )
                    continue

                canonical_rate = rate_value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
                existing_rate = db.query(ExchangeRate).filter(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency
                ).first()

                if existing_rate:
                    existing_rate.rate = canonical_rate
                    updated_count += 1
                else:
                    db.add(ExchangeRate(
                        from_currency=from_currency,
                        to_currency=to_currency,
                        rate=canonical_rate
                    ))
                    created_count += 1

        db.commit()
        total_count = updated_count + created_count
        logger.info(
            "Exchange rate refresh complete using one EUR-based request: %d updated, %d created",
            updated_count,
            created_count,
        )
        return total_count
