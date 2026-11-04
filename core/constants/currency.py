from enum import Enum


class Currency(str, Enum):
    """Supported currencies for the Multi-Currency Budgeting API."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v2/rates"
EXCHANGE_BASE_CURRENCY = Currency.EUR
SUPPORTED_CURRENCIES = [Currency.GBP, Currency.USD, Currency.EUR]
