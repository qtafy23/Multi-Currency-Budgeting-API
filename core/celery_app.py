from datetime import timedelta

from celery import Celery
from celery.signals import beat_init

from core.config.settings import settings

celery_app = Celery(
    "multi_currency_budgeting_api",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["apps.exchange.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
)

if settings.exchange_rate_update_interval_minutes > 0:
    celery_app.conf.beat_schedule = {
        "refresh-exchange-rates": {
            "task": "apps.exchange.tasks.refresh_exchange_rates",
            "schedule": timedelta(
                minutes=settings.exchange_rate_update_interval_minutes
            ),
            "options": {"expires": 300},
        }
    }

# Autodiscover tasks in the exchange app package
celery_app.autodiscover_tasks(["apps.exchange"])

# Import the module that defines scheduled exchange rate tasks
import apps.exchange.tasks  # noqa: F401, E402


def enqueue_startup_exchange_rate_refresh(sender=None, **kwargs):
    scheduler = getattr(sender, "scheduler", None)
    entry = (
        scheduler.schedule.get("refresh-exchange-rates")
        if scheduler is not None
        else None
    )

    if entry is not None and entry.is_due()[0]:
        return

    celery_app.send_task("apps.exchange.tasks.refresh_exchange_rates")
    if entry is not None:
        scheduler.reserve(entry)


beat_init.connect(enqueue_startup_exchange_rate_refresh, weak=False)
