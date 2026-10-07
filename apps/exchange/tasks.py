import logging

from celery import Task

from apps.exchange.services import ExchangeRateService
from core.celery_app import celery_app
from core.db.db import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="apps.exchange.tasks.refresh_exchange_rates",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    acks_late=True,
)
def refresh_exchange_rates(self: Task):
    """
    Periodic task to refresh exchange rates from Frankfurter API.

    Runs on a schedule defined in Celery Beat configuration.
    Updates existing exchange rate records and creates missing ones.
    """
    logger.info("Starting scheduled exchange rate refresh from Frankfurter")
    db = SessionLocal()
    try:
        total_updated = ExchangeRateService.refresh_rates_from_frankfurter(
            db, timeout_seconds=10
        )
        logger.info(
            "Exchange rate refresh completed successfully, %d rates updated",
            total_updated,
        )
        return {"updated": total_updated}
    except Exception as exc:
        logger.error("Exchange rate refresh failed (%s)", type(exc).__name__)
        db.rollback()
        safe_error = RuntimeError(
            f"Exchange rate refresh failed ({type(exc).__name__})"
        )
        raise self.retry(exc=safe_error) from None
    finally:
        db.close()
