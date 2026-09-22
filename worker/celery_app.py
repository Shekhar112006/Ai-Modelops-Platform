from __future__ import annotations

from celery import Celery

from backend.app.core.config import settings


celery_app = Celery(
    "modelops",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(
    ["worker"]
)
