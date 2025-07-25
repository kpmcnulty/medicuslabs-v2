from celery import Celery
import os

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "medical_data",
    broker=redis_url,
    backend=redis_url,
    include=["tasks.scrapers", "tasks.scheduled", "tasks.web_scrapers"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)