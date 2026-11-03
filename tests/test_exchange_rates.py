from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from apps.exchange.models import ExchangeRate
from apps.exchange.services import ExchangeRateService
from core.config.settings import Settings, settings
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


@pytest.fixture
def rate_now(monkeypatch):
    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr("apps.exchange.services.datetime", FixedDatetime)
    return now


def test_missing_rate_is_a_dependency_error(db_session):
    with pytest.raises(HTTPException) as exc:
        ExchangeRateService.convert_amount(
            db_session, Currency.USD, Currency.EUR, Decimal("10")
        )
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "exchange_rate_unavailable"
    assert exc.value.detail["from_currency"] == "USD"
    assert exc.value.detail["to_currency"] == "EUR"


@pytest.mark.parametrize("age_hours", [47, 48, 49])
def test_rate_expiration_boundary(db_session, rate_now, age_hours):
    db_session.add(ExchangeRate(
        from_currency=Currency.USD, to_currency=Currency.EUR,
        rate=Decimal("0.9"),
        updated_at=rate_now - timedelta(hours=age_hours),
    ))
    db_session.commit()
    if age_hours < 48:
        assert ExchangeRateService.convert_amount(
            db_session, Currency.USD, Currency.EUR, Decimal("10")
        ) == Decimal("9.00")
    else:
        with pytest.raises(HTTPException) as exc:
            ExchangeRateService.convert_amount(
                db_session, Currency.USD, Currency.EUR, Decimal("10")
            )
        assert exc.value.status_code == 503
        assert exc.value.detail["code"] == "exchange_rate_stale"


def test_unknown_refresh_time_is_stale(db_session):
    db_session.add(ExchangeRate(
        from_currency=Currency.USD, to_currency=Currency.EUR,
        rate=Decimal("0.9"),
    ))
    db_session.commit()
    db_session.execute(text("UPDATE exchange_rates SET updated_at = NULL"))
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        ExchangeRateService.get_rate(db_session, Currency.USD, Currency.EUR)
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "exchange_rate_stale"
    assert exc.value.detail["updated_at"] is None


def test_freshness_threshold_is_configurable(
    db_session, monkeypatch, rate_now,
):
    monkeypatch.setattr(settings, "exchange_rate_max_age_hours", 1)
    db_session.add(ExchangeRate(
        from_currency=Currency.USD, to_currency=Currency.EUR,
        rate=Decimal("0.9"), updated_at=rate_now - timedelta(hours=2),
    ))
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        ExchangeRateService.get_rate(db_session, Currency.USD, Currency.EUR)
    assert exc.value.detail["code"] == "exchange_rate_stale"


@pytest.mark.parametrize("hours", [0, -1])
def test_freshness_threshold_must_be_positive(hours):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, exchange_rate_max_age_hours=hours)


def test_same_currency_needs_no_rate(db_session):
    assert ExchangeRateService.convert_amount(
        db_session, Currency.USD, Currency.USD, Decimal("12.345")
    ) == Decimal("12.35")


def test_refresh_advances_timestamp_even_if_rate_does_not_change(
    db_session, monkeypatch, rate_now,
):
    db_session.add(ExchangeRate(
        from_currency=Currency.EUR, to_currency=Currency.USD,
        rate=Decimal("1.1"), updated_at=rate_now - timedelta(days=3),
    ))
    db_session.commit()
    monkeypatch.setattr(
        ExchangeRateService, "fetch_from_frankfurter",
        lambda *args: {"USD": Decimal("1.1"), "GBP": Decimal("0.8")},
    )
    assert ExchangeRateService.refresh_rates_from_frankfurter(db_session) == 6
    rates = db_session.query(ExchangeRate).all()
    assert len(rates) == 6
    assert all(r.updated_at == rate_now.replace(tzinfo=None) for r in rates)
    assert ExchangeRateService.convert_amount(
        db_session, Currency.EUR, Currency.USD, Decimal("10")
    ) == Decimal("11.00")


@pytest.mark.parametrize("payload", [
    None, {}, {"USD": Decimal("1.1")},
    {"USD": Decimal("1.1"), "GBP": Decimal("0")},
    {"USD": Decimal("1.1"), "GBP": Decimal("-1")},
    {"USD": Decimal("1.1"), "GBP": Decimal("NaN")},
    {"USD": Decimal("1.1"), "GBP": Decimal("Infinity")},
])
def test_failed_refresh_preserves_values_and_timestamp(
    db_session, monkeypatch, rate_now, payload,
):
    previous = rate_now.replace(tzinfo=None) - timedelta(days=3)
    db_session.add(ExchangeRate(
        from_currency=Currency.EUR, to_currency=Currency.USD,
        rate=Decimal("1.1"), updated_at=previous,
    ))
    db_session.commit()
    monkeypatch.setattr(
        ExchangeRateService, "fetch_from_frankfurter", lambda *args: payload
    )
    with pytest.raises(RuntimeError):
        ExchangeRateService.refresh_rates_from_frankfurter(db_session)
    db_session.commit()
    rate = db_session.query(ExchangeRate).one()
    assert rate.rate == Decimal("1.1")
    assert rate.updated_at == previous


def test_rate_resource_can_be_inspected_even_when_stale(db_session, rate_now):
    rate = ExchangeRate(
        from_currency=Currency.USD, to_currency=Currency.EUR,
        rate=Decimal("0.9"), updated_at=rate_now - timedelta(days=3),
    )
    db_session.add(rate)
    db_session.commit()
    found = ExchangeRateService.get_rate_by_id(db_session, rate.id)
    assert found.id == rate.id
    with pytest.raises(HTTPException) as exc:
        ExchangeRateService.get_rate_by_id(db_session, rate.id + 1)
    assert exc.value.status_code == 404
