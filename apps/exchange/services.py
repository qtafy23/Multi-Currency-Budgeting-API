import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

import requests
from fastapi import HTTPException, status
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from apps.exchange.models import ExchangeRate
from core.constants.currency import Currency
from core.constants.currencylayer import CurrencyLayerConfig, CurrencyLayerResponseKeys

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """
    Service layer for exchange rate operations.
    Rates are system-managed exclusively via CurrencyLayer API and Celery tasks.
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
    def fetch_from_currencylayer(
        base_currency: Currency,
        target_currencies: list[Currency],
        api_key: str,
        base_url: str,
        timeout_seconds: int = 10
    ) -> Optional[Dict[str, Decimal]]:
        """
        Fetch exchange rates from CurrencyLayer API.
        
        Returns a dict mapping target currency code -> rate value, or None on error.
        """
        if not api_key:
            logger.error("CurrencyLayer API key is not configured")
            return None

        currency_codes = ",".join(curr.value for curr in target_currencies)
        url = f"{base_url}{CurrencyLayerConfig.LIVE_ENDPOINT}"
        params = {
            "access_key": api_key,
            "source": base_currency.value,
            "currencies": currency_codes,
            "format": "1",
        }

        def _call_currencylayer(request_params: dict) -> Optional[dict]:
            try:
                logger.debug(
                    "Fetching exchange rates from CurrencyLayer for params %s",
                    request_params,
                )
                response = requests.get(url, params=request_params, timeout=timeout_seconds)
                response.raise_for_status()
                return response.json()
            except RequestException as exc:
                logger.exception(
                    "Failed to call CurrencyLayer for source %s",
                    request_params.get("source"),
                    exc_info=exc,
                )
                return None

        payload = _call_currencylayer(params)
        if payload is None:
            return None

        if not payload.get(CurrencyLayerResponseKeys.SUCCESS):
            error_info = payload.get(CurrencyLayerResponseKeys.ERROR, {})
            logger.warning(
                "CurrencyLayer API returned error for source %s: %s",
                base_currency.value,
                error_info,
            )

            # Fallback to USD-based quotes if non-USD source is not available
            if base_currency.value != Currency("USD").value:
                usd_currencies = {base_currency.value} | {c.value for c in target_currencies}
                usd_params = {
                    "access_key": api_key,
                    "source": "USD",
                    "currencies": ",".join(sorted(usd_currencies)),
                    "format": "1",
                }
                usd_payload = _call_currencylayer(usd_params)
                if not usd_payload or not usd_payload.get(CurrencyLayerResponseKeys.SUCCESS):
                    logger.error(
                        "USD fallback failed for deriving rates for source %s",
                        base_currency.value,
                    )
                    return None

                usd_quotes = usd_payload.get(CurrencyLayerResponseKeys.QUOTES, {})
                if not isinstance(usd_quotes, dict):
                    logger.error("Invalid quotes structure in USD fallback response")
                    return None

                try:
                    usd_map: dict[str, Decimal] = {}
                    for quote_key, quote_value in usd_quotes.items():
                        usd_map[quote_key[-3:]] = Decimal(str(quote_value))

                    base_usd = usd_map.get(base_currency.value)
                    if base_usd is None:
                        logger.error(
                            "USD fallback missing USD->%s quote",
                            base_currency.value,
                        )
                        return None

                    derived_rates: dict[str, Decimal] = {}
                    for target_currency in target_currencies:
                        target_usd = usd_map.get(target_currency.value)
                        if target_usd is None:
                            logger.warning(
                                "USD fallback missing USD->%s quote; skipping",
                                target_currency.value,
                            )
                            continue

                        derived_rate = target_usd / base_usd
                        derived_rates[target_currency.value] = derived_rate
                    return derived_rates
                except (TypeError, ValueError) as exc:
                    logger.exception(
                        "Failed to derive exchange rates from USD fallback",
                        exc_info=exc,
                    )
                    return None

            logger.error(
                "CurrencyLayer source %s unavailable and no fallback applied",
                base_currency.value,
            )
            return None

        quotes = payload.get(CurrencyLayerResponseKeys.QUOTES, {})
        if not isinstance(quotes, dict):
            logger.error("Invalid quotes structure in CurrencyLayer response")
            return None

        try:
            rates = {}
            for quote_key, quote_value in quotes.items():
                # Quote key format: "GBPUSD" means 1 GBP = quote_value USD
                # Extract target currency (last 3 chars)
                target_ccy = quote_key[-3:]
                rates[target_ccy] = Decimal(str(quote_value))
            return rates
        except (TypeError, ValueError) as exc:
            logger.exception(
                "Failed to parse exchange rates from CurrencyLayer response",
                exc_info=exc
            )
            return None

    @staticmethod
    def refresh_rates_from_currencylayer(
        db: Session,
        api_key: str,
        base_url: str,
        timeout_seconds: int = 10
    ) -> int:
        """
        Refresh all required exchange rates from CurrencyLayer.
        
        Updates existing records and creates missing ones.
        Returns the total number of rates updated/created.
        """
        supported_currencies = [Currency(c) for c in CurrencyLayerConfig.SUPPORTED_CURRENCIES]
        total_count = 0

        for base_currency in supported_currencies:
            target_currencies = [
                Currency(c) for c in CurrencyLayerConfig.REQUIRED_PAIRS.get(base_currency.value, [])
            ]

            if not target_currencies:
                logger.debug("No target currencies for base %s", base_currency.value)
                continue

            rates = ExchangeRateService.fetch_from_currencylayer(
                base_currency,
                target_currencies,
                api_key,
                base_url,
                timeout_seconds
            )

            if rates is None:
                logger.warning("Failed to fetch rates for base %s", base_currency.value)
                continue

            updated_count = 0
            created_count = 0

            for target_currency in target_currencies:
                rate_value = rates.get(target_currency.value)
                if rate_value is None:
                    logger.warning(
                        "No rate received from CurrencyLayer for %s -> %s",
                        base_currency.value,
                        target_currency.value
                    )
                    continue

                canonical_rate = rate_value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

                existing_rate = db.query(ExchangeRate).filter(
                    ExchangeRate.from_currency == base_currency,
                    ExchangeRate.to_currency == target_currency
                ).first()

                if existing_rate:
                    existing_rate.rate = canonical_rate
                    updated_count += 1
                else:
                    db.add(
                        ExchangeRate(
                            from_currency=base_currency,
                            to_currency=target_currency,
                            rate=canonical_rate
                        )
                    )
                    created_count += 1

            db.commit()
            count = updated_count + created_count
            total_count += count
            logger.info(
                "Processed base %s: %d updated, %d created",
                base_currency.value,
                updated_count,
                created_count
            )

        logger.info("Exchange rate refresh complete: %d total rates updated/created", total_count)
        return total_count
