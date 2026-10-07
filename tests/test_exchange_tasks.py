import pytest
from celery.signals import beat_init

from apps.exchange.tasks import refresh_exchange_rates
from core.celery_app import celery_app


class DummySession:
    def rollback(self):
        pass

    def close(self):
        pass


def test_refresh_exchange_rates_returns_updated_count(monkeypatch):
    monkeypatch.setattr(
        "apps.exchange.tasks.SessionLocal", lambda: DummySession()
    )
    monkeypatch.setattr(
        "apps.exchange.tasks.ExchangeRateService."
        "refresh_rates_from_frankfurter",
        lambda db, timeout_seconds=10: 6,
    )

    result = refresh_exchange_rates.run()

    assert result == {"updated": 6}


def test_beat_start_enqueues_one_refresh_and_resets_interval(monkeypatch):
    class FakeEntry:
        def is_due(self):
            return False, 3600

    class FakeScheduler:
        def __init__(self):
            self.entry = FakeEntry()
            self.schedule = {"refresh-exchange-rates": self.entry}
            self.reserved = []

        def reserve(self, entry):
            self.reserved.append(entry)

    enqueued_tasks = []
    scheduler = FakeScheduler()
    beat = type("Beat", (), {"scheduler": scheduler})()
    monkeypatch.setattr(
        celery_app,
        "send_task",
        lambda task_name: enqueued_tasks.append(task_name),
    )

    beat_init.send(sender=beat)

    assert enqueued_tasks == ["apps.exchange.tasks.refresh_exchange_rates"]
    assert scheduler.reserved == [scheduler.entry]


def test_beat_start_does_not_duplicate_a_due_scheduled_refresh(monkeypatch):
    class FakeEntry:
        def is_due(self):
            return True, 0

    class FakeScheduler:
        schedule = {"refresh-exchange-rates": FakeEntry()}

    enqueued_tasks = []
    beat = type("Beat", (), {"scheduler": FakeScheduler()})()
    monkeypatch.setattr(
        celery_app,
        "send_task",
        lambda task_name: enqueued_tasks.append(task_name),
    )

    beat_init.send(sender=beat)

    assert enqueued_tasks == []


def test_refresh_exchange_rates_handles_provider_error(monkeypatch):
    monkeypatch.setattr(
        "apps.exchange.tasks.SessionLocal", lambda: DummySession()
    )

    def raise_runtime_error(db, timeout_seconds=10):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "apps.exchange.tasks.ExchangeRateService."
        "refresh_rates_from_frankfurter",
        raise_runtime_error,
    )

    with pytest.raises(RuntimeError, match="Exchange rate refresh failed"):
        refresh_exchange_rates.run()
