from __future__ import annotations

from celery import Celery
from celery.signals import (
    setup_logging,
    task_failure,
    task_postrun,
    task_prerun,
    worker_process_shutdown,
)

from worker import task_metrics

from backend.app.core.config import settings
from backend.app.core.logging_config import configure_logging


@setup_logging.connect
def configure_celery_logging(**kwargs: object) -> None:
    """Use shared JSON logging instead of Celery's default formatting."""
    configure_logging("modelops-worker")


# Record task lifecycle metrics across Celery worker processes.
task_prerun.connect(
    task_metrics.record_task_prerun,
    weak=False,
)
task_postrun.connect(
    task_metrics.record_task_postrun,
    weak=False,
)
task_failure.connect(
    task_metrics.record_task_failure,
    weak=False,
)
worker_process_shutdown.connect(
    task_metrics.mark_worker_process_dead,
    weak=False,
)


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
    beat_schedule={
        "deployment-health-check-every-minute": {
            "task": "modelops.check_deployment_health",
            "schedule": settings.health_check_interval_seconds,
        },
    },
)

celery_app.autodiscover_tasks(
    ["worker"]
)
