from __future__ import annotations

from backend.app.core.config import settings
from worker.celery_app import celery_app
from worker.tasks import check_deployment_health


def test_deployment_health_check_is_scheduled() -> None:
    """Health monitoring must have a periodic Celery Beat schedule."""

    schedule = celery_app.conf.beat_schedule

    entry = schedule.get("deployment-health-check-every-minute")

    assert entry is not None
    assert entry["task"] == "modelops.check_deployment_health"
    assert entry["schedule"] == settings.health_check_interval_seconds
    assert settings.health_check_interval_seconds > 0
    assert check_deployment_health.name == "modelops.check_deployment_health"
