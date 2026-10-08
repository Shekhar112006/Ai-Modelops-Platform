from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from model_router.main import app
from model_router import main as router_main


client = TestClient(app)

PROJECT_ID = UUID(
    "09cb523e-bd8c-4dfa-81ce-ae7a4e616d99"
)


class FakeSessionContext:
    """Provide a minimal async session context for router tests."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSessionFactory:
    """Return the fake session context."""

    def __call__(self):
        return FakeSessionContext()


class FakeDeploymentRepository:
    """Return a controlled deployment for testing."""

    def __init__(self, deployment=None):
        self.deployment = deployment

    async def list_routable_by_project(
        self,
        session,
        project_id,
        environment,
    ):
        if self.deployment is None:
            return []

        return [self.deployment]


class FakeModelServerClient:
    """Capture the endpoint used by the router."""

    last_base_url: str | None = None
    last_features: list[float] | None = None

    def __init__(self, base_url: str):
        self.base_url = base_url
        FakeModelServerClient.last_base_url = base_url

    async def predict(self, features):
        FakeModelServerClient.last_features = features

        return {
            "model_name": "demo-classifier",
            "model_version": "5",
            "prediction": [0],
        }


def test_router_health() -> None:
    """The router process should report healthy."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
    }


def test_prediction_uses_active_deployment(monkeypatch) -> None:
    """The router should use the endpoint from the active deployment."""

    deployment = SimpleNamespace(
        id="deployment-1",
        model_name="demo-classifier",
        model_version="5",
        environment="staging",
        status="staging",
        traffic_percentage=100,
        model_endpoint="http://model-server-test:8000",
    )

    monkeypatch.setattr(
        router_main,
        "AsyncSessionFactory",
        FakeSessionFactory(),
    )

    monkeypatch.setattr(
        router_main,
        "deployment_repository",
        FakeDeploymentRepository(deployment),
    )

    monkeypatch.setattr(
        router_main,
        "ModelServerClient",
        FakeModelServerClient,
    )

    response = client.post(
        "/predict",
        json={
            "project_id": str(PROJECT_ID),
            "features": [0.0] * 10,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model_name"] == "demo-classifier"
    assert data["model_version"] == "5"
    assert data["prediction"] == [0]

    assert (
        FakeModelServerClient.last_base_url
        == "http://model-server-test:8000"
    )

    assert (
        FakeModelServerClient.last_features
        == [0.0] * 10
    )


def test_prediction_without_active_deployment() -> None:
    """The router should reject requests without an active deployment."""

    class NoDeploymentRepository:
        async def list_routable_by_project(
            self,
            session,
            project_id,
            environment,
        ):
            return []


    original_factory = router_main.AsyncSessionFactory
    original_repository = router_main.deployment_repository

    router_main.AsyncSessionFactory = FakeSessionFactory()
    router_main.deployment_repository = NoDeploymentRepository()

    try:
        response = client.post(
            "/predict",
            json={
                "project_id": str(PROJECT_ID),
                "features": [0.0] * 10,
            },
        )
    finally:
        router_main.AsyncSessionFactory = original_factory
        router_main.deployment_repository = original_repository

    assert response.status_code == 404


def test_invalid_feature_count() -> None:
    """The router should reject requests that do not contain ten features."""

    response = client.post(
        "/predict",
        json={
            "project_id": str(PROJECT_ID),
            "features": [0.0] * 9,
        },
    )

    assert response.status_code == 422
