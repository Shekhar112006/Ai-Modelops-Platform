from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.services import deployment_recovery_executor as executor


class FakeAsyncSession:
    def __init__(self) -> None:
        self.rollback_called = False

    async def rollback(self) -> None:
        self.rollback_called = True


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


def test_executor_returns_rolled_back_deployment(monkeypatch) -> None:
    deployment_id = uuid4()
    fake_session = FakeAsyncSession()
    fake_result = SimpleNamespace(
        id=deployment_id,
        status="rolled_back",
    )

    class FakeDeploymentService:
        async def rollback_canary_deployment(
            self,
            session,
            requested_id,
        ):
            assert session is fake_session
            assert requested_id == deployment_id
            return fake_result

    monkeypatch.setattr(
        executor,
        "AsyncSessionFactory",
        lambda: FakeAsyncSessionContext(fake_session),
    )
    monkeypatch.setattr(
        executor,
        "DeploymentService",
        FakeDeploymentService,
    )

    result = executor.execute_automated_rollback(deployment_id)

    assert result == {
        "deployment_id": str(deployment_id),
        "status": "rolled_back",
    }
    assert fake_session.rollback_called is False


def test_executor_rolls_back_transaction_when_service_fails(
    monkeypatch,
) -> None:
    deployment_id = uuid4()
    fake_session = FakeAsyncSession()

    class FailingDeploymentService:
        async def rollback_canary_deployment(
            self,
            session,
            requested_id,
        ):
            raise ValueError("No safe stable deployment was found.")

    monkeypatch.setattr(
        executor,
        "AsyncSessionFactory",
        lambda: FakeAsyncSessionContext(fake_session),
    )
    monkeypatch.setattr(
        executor,
        "DeploymentService",
        FailingDeploymentService,
    )

    with pytest.raises(
        ValueError,
        match="No safe stable deployment",
    ):
        executor.execute_automated_rollback(deployment_id)

    assert fake_session.rollback_called is True
