from decimal import Decimal

from apps.exchange.models import ExchangeRate
from apps.exchange.services import ExchangeRateService
from core.constants.currency import Currency, FRANKFURTER_RATES_URL


def test_fetch_from_frankfurter_parses_latest_dict_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"base": "EUR", "quote": "USD", "rate": 1.1},
                {"base": "EUR", "quote": "GBP", "rate": 0.8},
            ]

    request = {}

    def fake_get(url, params, timeout):
        request.update(url=url, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("apps.exchange.services.requests.get", fake_get)

    result = ExchangeRateService.fetch_from_frankfurter(
        Currency.EUR,
        [Currency.USD, Currency.GBP],
        timeout_seconds=5,
    )

    assert result == {
        "USD": Decimal("1.1"),
        "GBP": Decimal("0.8"),
    }
    assert request == {
        "url": FRANKFURTER_RATES_URL,
        "params": {"base": "EUR", "quotes": "USD,GBP"},
        "timeout": 5,
    }


def test_refresh_rates_from_frankfurter_updates_and_creates_pairs(
    db_session, monkeypatch
):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"rates": {"USD": 1.1, "GBP": 0.8}, "base": "EUR"}

    monkeypatch.setattr(
        "apps.exchange.services.requests.get",
        lambda *args, **kwargs: FakeResponse(),
    )

    stale = ExchangeRate(
        from_currency=Currency.GBP,
        to_currency=Currency.USD,
        rate=Decimal("0.10"),
    )
    db_session.add(stale)
    db_session.commit()

    updated = ExchangeRateService.refresh_rates_from_frankfurter(
        db_session, timeout_seconds=5
    )

    assert updated == 6
    pair = (
        db_session.query(ExchangeRate)
        .filter(
            ExchangeRate.from_currency == Currency.GBP,
            ExchangeRate.to_currency == Currency.USD,
        )
        .one()
    )
    assert Decimal(str(pair.rate)) == Decimal("1.375")
    assert db_session.query(ExchangeRate).count() == 6


def test_convert_amount_uses_stored_pair_rate(db_session):
    db_session.add(
        ExchangeRate(
            from_currency=Currency.GBP,
            to_currency=Currency.USD,
            rate=Decimal("1.25"),
        )
    )
    db_session.commit()

    result = ExchangeRateService.convert_amount(
        db_session,
        Currency.GBP,
        Currency.USD,
        Decimal("10.00"),
    )

    assert result == Decimal("12.50")
