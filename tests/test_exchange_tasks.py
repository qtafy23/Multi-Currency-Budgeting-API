import pytest

from apps.exchange.tasks import refresh_exchange_rates


class DummySession:
    def rollback(self):
        pass

    def close(self):
        pass


def test_refresh_exchange_rates_returns_updated_count(monkeypatch):
    monkeypatch.setattr("apps.exchange.tasks.SessionLocal", lambda: DummySession())
    monkeypatch.setattr(
        "apps.exchange.tasks.ExchangeRateService.refresh_rates_from_frankfurter",
        lambda db, timeout_seconds=10: 6,
    )

    result = refresh_exchange_rates.run()

    assert result == {"updated": 6}


def test_refresh_exchange_rates_handles_provider_error(monkeypatch):
    monkeypatch.setattr("apps.exchange.tasks.SessionLocal", lambda: DummySession())

    def raise_runtime_error(db, timeout_seconds=10):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "apps.exchange.tasks.ExchangeRateService.refresh_rates_from_frankfurter",
        raise_runtime_error,
    )

    with pytest.raises(RuntimeError, match="Exchange rate refresh failed"):
        refresh_exchange_rates.run()
