from celery import Celery
from core.config.settings import settings

celery_app = Celery(
    "multi_currency_budgeting_api",
    broker=settings.redis_url,
    backend=settings.redis_url,
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

# Register task modules from the application when they are defined.
# Import the module that defines tasks from within the task package,
# rather than hard-coding a temporary example task here.
