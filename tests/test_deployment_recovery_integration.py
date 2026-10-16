from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import httpx

import worker.tasks as task_module
from backend.app.repositories import (
    deployment_health_check_repository as health_repository_module,
    deployment_recovery_event_repository as recovery_repository_module,
)
from backend.app.services import (
    deployment_recovery_executor as executor_module,
)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeHealthRepository:
    def __init__(self, deployment, previous) -> None:
        self.deployment = deployment
        self.previous = previous
        self.records = []

    def list_monitorable_deployments(self, session):
        return [self.deployment]

    def get_latest_for_deployment(self, session, deployment_id):
        return self.previous

    def create(self, session, **kwargs):
        record = SimpleNamespace(**kwargs)
        self.records.append(record)
        return record


class FakeRecoveryRepository:
    last_instance = None

    def __init__(self) -> None:
        self.events = []
        type(self).last_instance = self

    def create(self, session, **kwargs):
        event = SimpleNamespace(**kwargs)
        self.events.append(event)
        return event


class FakeHTTPClient:
    def __init__(
        self,
        status_code: int,
        restored_status_code: int = 200,
    ) -> None:
        self.status_code = status_code
        self.restored_status_code = restored_status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, url: str):
        status_code = (
            self.restored_status_code
            if "stable-model" in url
            else self.status_code
        )
        return httpx.Response(
            status_code,
            request=httpx.Request("GET", url),
        )


def run_task(
    monkeypatch,
    *,
    status_code: int,
    previous_failures: int | None,
    rollback_error: Exception | None = None,
    restored_status_code: int = 200,
):
    deployment_id = uuid4()
    deployment = SimpleNamespace(
        id=deployment_id,
        model_name="demo-classifier",
        model_version="5",
        environment="production",
        status="production",
        model_endpoint="http://model-test:8000",
    )
    previous = (
        SimpleNamespace(consecutive_failures=previous_failures)
        if previous_failures is not None
        else None
    )

    session = FakeSession()
    health_repository = FakeHealthRepository(deployment, previous)
    recovery_repository = FakeRecoveryRepository()
    rollback_calls = []
    restored_deployment_id = uuid4()

    def fake_rollback(requested_id):
        rollback_calls.append(requested_id)
        if rollback_error is not None:
            raise rollback_error
        return {
            "deployment_id": str(requested_id),
            "status": "rolled_back",
            "restored_deployment_id": str(restored_deployment_id),
            "restored_model_name": "demo-classifier",
            "restored_model_version": "5",
            "restored_model_endpoint": "http://stable-model:8000",
            "restored_status": "staging",
            "restored_traffic_percentage": "100",
        }

    monkeypatch.setattr(task_module, "get_session", lambda: session)
    monkeypatch.setattr(
        health_repository_module,
        "DeploymentHealthCheckRepository",
        lambda: health_repository,
    )
    monkeypatch.setattr(
        recovery_repository_module,
        "DeploymentRecoveryEventRepository",
        lambda: recovery_repository,
    )
    monkeypatch.setattr(
        executor_module,
        "execute_automated_rollback",
        fake_rollback,
    )
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda timeout: FakeHTTPClient(
            status_code,
            restored_status_code,
        ),
    )

    result = task_module.check_deployment_health()

    return (
        result,
        session,
        health_repository,
        recovery_repository,
        rollback_calls,
        deployment_id,
    )


def event_types(repository):
    return [event.event_type for event in repository.events]


def test_threshold_crossing_executes_and_records_rollback(monkeypatch):
    result, session, _, events, calls, deployment_id = run_task(
        monkeypatch,
        status_code=503,
        previous_failures=2,
    )

    assert calls == [deployment_id]
    assert event_types(events) == [
        "failure_threshold_reached",
        "rollback_started",
        "rollback_succeeded",
        "restoration_verification_succeeded",
    ]
    assert result["recovery_candidates"] == 1
    assert result["results"][0]["recovery"]["status"] == "succeeded"
    assert result["results"][0]["recovery"]["reason"] == (
        "restoration_verified"
    )
    assert session.commits == 3
    assert session.closed


def test_rollback_failure_is_persisted(monkeypatch):
    result, session, _, events, calls, deployment_id = run_task(
        monkeypatch,
        status_code=503,
        previous_failures=2,
        rollback_error=ValueError("No safe stable deployment was found."),
    )

    assert calls == [deployment_id]
    assert event_types(events) == [
        "failure_threshold_reached",
        "rollback_started",
        "rollback_failed",
    ]
    assert "No safe stable deployment" in events.events[-1].details["error"]
    assert result["results"][0]["recovery"]["status"] == "failed"
    assert session.commits == 2
    assert session.rollbacks == 1
    assert session.closed


def test_below_threshold_does_not_execute_rollback(monkeypatch):
    result, _, _, events, calls, _ = run_task(
        monkeypatch,
        status_code=503,
        previous_failures=1,
    )

    assert calls == []
    assert events.events == []
    assert result["recovery_candidates"] == 0
    assert result["results"][0]["recovery"]["attempted"] is False


def test_first_failure_is_recorded_without_rollback(monkeypatch):
    result, _, _, events, calls, _ = run_task(
        monkeypatch,
        status_code=503,
        previous_failures=None,
    )

    assert calls == []
    assert event_types(events) == ["health_check_failed"]
    assert result["results"][0]["consecutive_failures"] == 1


def test_recovery_after_failure_is_recorded(monkeypatch):
    result, _, _, events, calls, _ = run_task(
        monkeypatch,
        status_code=200,
        previous_failures=3,
    )

    assert calls == []
    assert event_types(events) == ["deployment_health_recovered"]
    assert result["results"][0]["consecutive_failures"] == 0


def test_restoration_verification_failure_is_persisted(
    monkeypatch,
) -> None:
    """A rollback isn't considered healthy if the restored model returns 503."""

    result, session, _, events, calls, deployment_id = run_task(
        monkeypatch,
        status_code=503,
        previous_failures=2,
        restored_status_code=503,
    )

    assert calls == [deployment_id]
    assert event_types(events) == [
        "failure_threshold_reached",
        "rollback_started",
        "rollback_succeeded",
        "restoration_verification_failed",
    ]

    verification_event = events.events[-1]
    assert verification_event.severity == "error"
    assert verification_event.details["restored_health_status_code"] == 503
    assert verification_event.details["restoration_verified"] is False

    recovery = result["results"][0]["recovery"]
    assert recovery["attempted"] is True
    assert recovery["status"] == "verification_failed"
    assert recovery["restored_health_status_code"] == 503
    assert session.commits == 3
    assert session.closed
