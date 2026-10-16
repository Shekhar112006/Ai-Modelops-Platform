from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.services import deployment_recovery_executor as executor


class FakeAsyncSession:
    def __init__(self) -> None:
        self.rollback_called = False
        self.refreshed = []

    async def rollback(self) -> None:
        self.rollback_called = True

    async def refresh(self, entity) -> None:
        self.refreshed.append(entity)


class FakeAsyncSessionContext:
    def __init__(self, session: FakeAsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeAsyncSession:
        return self.session

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> bool:
        return False


def configure_executor(monkeypatch, rollback_error=None):
    failed_id = uuid4()
    stable_id = uuid4()
    project_id = uuid4()

    failed = SimpleNamespace(
        id=failed_id,
        project_id=project_id,
        model_name="demo-classifier",
        model_version="6",
        environment="staging",
        status="canary",
        traffic_percentage=5,
        model_endpoint="http://failed-model:8000",
    )

    stable = SimpleNamespace(
        id=stable_id,
        project_id=project_id,
        model_name="demo-classifier",
        model_version="5",
        environment="staging",
        status="staging",
        traffic_percentage=95,
        model_endpoint="http://stable-model:8000",
    )

    session = FakeAsyncSession()

    class FakeDeploymentRepository:
        async def get_by_id(self, active_session, requested_id):
            return {
                failed_id: failed,
                stable_id: stable,
            }.get(requested_id)

        async def list_by_project(self, active_session, requested_project):
            assert requested_project == project_id
            return [failed, stable]

    repository = FakeDeploymentRepository()

    class FakeDeploymentService:
        def __init__(self) -> None:
            self.deployment_repository = repository

        async def rollback_canary_deployment(
            self,
            active_session,
            requested_id,
        ):
            assert active_session is session
            assert requested_id == failed_id

            if rollback_error is not None:
                raise rollback_error

            failed.status = "rolled_back"
            failed.traffic_percentage = 0
            stable.traffic_percentage = 100
            return failed

    monkeypatch.setattr(
        executor,
        "AsyncSessionFactory",
        lambda: FakeAsyncSessionContext(session),
    )
    monkeypatch.setattr(
        executor,
        "DeploymentService",
        FakeDeploymentService,
    )

    return failed_id, stable, session


def test_executor_returns_restored_deployment_details(monkeypatch) -> None:
    failed_id, stable, session = configure_executor(monkeypatch)

    result = executor.execute_automated_rollback(failed_id)

    assert result["deployment_id"] == str(failed_id)
    assert result["status"] == "rolled_back"
    assert result["restored_deployment_id"] == str(stable.id)
    assert result["restored_model_name"] == "demo-classifier"
    assert result["restored_model_version"] == "5"
    assert result["restored_model_endpoint"] == (
        "http://stable-model:8000"
    )
    assert result["restored_status"] == "staging"
    assert result["restored_traffic_percentage"] == "100"
    assert stable in session.refreshed
    assert session.rollback_called is False


def test_executor_rolls_back_transaction_when_service_fails(
    monkeypatch,
) -> None:
    deployment_id, _, session = configure_executor(
        monkeypatch,
        rollback_error=ValueError("Rollback could not be completed."),
    )

    with pytest.raises(
        ValueError,
        match="Rollback could not be completed",
    ):
        executor.execute_automated_rollback(deployment_id)

    assert session.rollback_called is True
