from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import httpx

import worker.tasks as task_module
from backend.app.services import (
    deployment_recovery_executor as recovery_executor_module,
)
from backend.app.repositories import (
    deployment_health_check_repository as repository_module,
    deployment_recovery_event_repository as recovery_event_repository_module,
)


class FakeSession:
    """Minimal synchronous session for health-check task tests."""

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


class FakeRepository:
    """In-memory repository for health-check task tests."""

    def __init__(
        self,
        deployment,
        previous_check=None,
    ) -> None:
        self.deployment = deployment
        self.previous_check = previous_check
        self.created_records = []

    def list_monitorable_deployments(self, session):
        return [self.deployment]

    def get_latest_for_deployment(self, session, deployment_id):
        return self.previous_check

    def create(self, session, **kwargs):
        record = SimpleNamespace(**kwargs)
        self.created_records.append(record)
        return record


class FakeRecoveryEventRepository:
    """Capture recovery events in memory during task tests."""

    last_instance = None

    def __init__(self) -> None:
        self.events: list[SimpleNamespace] = []
        type(self).last_instance = self

    def create(self, session, **kwargs):
        event = SimpleNamespace(**kwargs)
        self.events.append(event)
        return event


class FakeHTTPClient:
    """Return a controlled HTTP response for health checks."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, url: str):
        request = httpx.Request("GET", url)
        return httpx.Response(
            status_code=self.status_code,
            request=request,
        )


def run_health_check(
    monkeypatch,
    *,
    status_code: int,
    previous_failures: int | None = None,
):
    deployment = SimpleNamespace(
        id=uuid4(),
        model_name="demo-classifier",
        model_version="5",
        environment="production",
        status="production",
        model_endpoint="http://model-test:8000",
    )

    previous_check = (
        SimpleNamespace(consecutive_failures=previous_failures)
        if previous_failures is not None
        else None
    )

    fake_session = FakeSession()
    fake_repository = FakeRepository(
        deployment,
        previous_check,
    )

    monkeypatch.setattr(
        task_module,
        "get_session",
        lambda: fake_session,
    )

    monkeypatch.setattr(
        repository_module,
        "DeploymentHealthCheckRepository",
        lambda: fake_repository,
    )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda timeout: FakeHTTPClient(status_code),
    )

    fake_recovery_repository = FakeRecoveryEventRepository()
    monkeypatch.setattr(
        recovery_event_repository_module,
        "DeploymentRecoveryEventRepository",
        lambda: fake_recovery_repository,
    )

    monkeypatch.setattr(
        recovery_executor_module,
        "execute_automated_rollback",
        lambda requested_id: {
            "deployment_id": str(requested_id),
            "status": "rolled_back",
        },
    )

    result = task_module.check_deployment_health()

    return result, fake_repository, fake_session


def test_healthy_endpoint_records_success_and_zero_failures(
    monkeypatch,
) -> None:
    result, repository, session = run_health_check(
        monkeypatch,
        status_code=200,
    )

    assert result["checked"] == 1
    assert result["healthy"] == 1
    assert result["unhealthy"] == 0

    record = repository.created_records[0]

    assert record.is_healthy is True
    assert record.status_code == 200
    assert record.consecutive_failures == 0
    assert record.error_message is None
    assert record.response_time_ms >= 0

    assert session.commits == 1
    assert session.closed is True


def test_unhealthy_endpoint_increments_failure_counter(
    monkeypatch,
) -> None:
    result, repository, session = run_health_check(
        monkeypatch,
        status_code=503,
        previous_failures=1,
    )

    assert result["checked"] == 1
    assert result["healthy"] == 0
    assert result["unhealthy"] == 1

    record = repository.created_records[0]

    assert record.is_healthy is False
    assert record.status_code == 503
    assert record.consecutive_failures == 2
    assert record.error_message is not None
    assert "HTTPStatusError" in record.error_message

    assert session.commits == 1
    assert session.closed is True


def test_recovered_endpoint_resets_failure_counter(
    monkeypatch,
) -> None:
    result, repository, session = run_health_check(
        monkeypatch,
        status_code=200,
        previous_failures=3,
    )

    assert result["healthy"] == 1
    assert result["unhealthy"] == 0

    record = repository.created_records[0]

    assert record.is_healthy is True
    assert record.consecutive_failures == 0
    assert record.error_message is None

    assert session.commits == 1
    assert session.closed is True



def test_third_consecutive_failure_marks_recovery_eligible(
    monkeypatch,
) -> None:
    """The configured failure threshold should identify recovery candidates."""

    result, repository, session = run_health_check(
        monkeypatch,
        status_code=503,
        previous_failures=2,
    )

    assert result["unhealthy"] == 1
    assert result["recovery_candidates"] == 1
    assert result["results"][0]["consecutive_failures"] == 3
    assert result["results"][0]["recovery_eligible"] is True

    assert session.closed is True


def test_failure_below_threshold_is_not_recovery_eligible(
    monkeypatch,
) -> None:
    """Fewer than three consecutive failures must not trigger recovery."""

    result, repository, session = run_health_check(
        monkeypatch,
        status_code=503,
        previous_failures=1,
    )

    assert result["unhealthy"] == 1
    assert result["recovery_candidates"] == 0
    assert result["results"][0]["consecutive_failures"] == 2
    assert result["results"][0]["recovery_eligible"] is False

    assert session.closed is True



def test_first_failure_records_health_check_failed_event(
    monkeypatch,
) -> None:
    result, _, _ = run_health_check(
        monkeypatch,
        status_code=503,
    )

    repository = FakeRecoveryEventRepository.last_instance
    assert repository is not None
    assert len(repository.events) == 1

    event = repository.events[0]
    assert event.event_type == "health_check_failed"
    assert event.severity == "warning"
    assert event.consecutive_failures == 1
    assert event.details["status_code"] == 503
    assert result["unhealthy"] == 1


def test_threshold_records_recovery_event(
    monkeypatch,
) -> None:
    result, _, _ = run_health_check(
        monkeypatch,
        status_code=503,
        previous_failures=2,
    )

    repository = FakeRecoveryEventRepository.last_instance
    assert repository is not None
    assert [
        event.event_type for event in repository.events
    ] == [
        "failure_threshold_reached",
        "rollback_started",
        "rollback_succeeded",
    ]

    event = repository.events[0]
    assert event.event_type == "failure_threshold_reached"
    assert event.severity == "error"
    assert event.consecutive_failures == 3
    assert event.details["failure_threshold"] == 3
    assert result["recovery_candidates"] == 1


def test_recovered_endpoint_records_recovery_event(
    monkeypatch,
) -> None:
    result, _, _ = run_health_check(
        monkeypatch,
        status_code=200,
        previous_failures=3,
    )

    repository = FakeRecoveryEventRepository.last_instance
    assert repository is not None
    assert len(repository.events) == 1

    event = repository.events[0]
    assert event.event_type == "deployment_health_recovered"
    assert event.severity == "info"
    assert event.consecutive_failures == 0
    assert result["healthy"] == 1

