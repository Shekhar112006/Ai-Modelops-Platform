from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from model_router import main as router_main
from model_router.main import app


client = TestClient(app)

PROJECT_ID = UUID(
    "09cb523e-bd8c-4dfa-81ce-ae7a4e616d99"
)


class FakeSession:
    """Minimal async session used by router tests."""

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeSessionFactory:
    """Return a fake async database session."""

    def __call__(self):
        return FakeSession()


class FakeDeploymentRepository:
    """Return stable and canary deployments."""

    def __init__(self, deployments):
        self.deployments = deployments

    async def list_routable_by_project(
        self,
        session,
        project_id,
        environment,
    ):
        return self.deployments


class FakeModelServerClient:
    """Return a prediction identifying the selected model."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def predict(self, features):
        version = (
            "5"
            if "canary" in self.base_url
            else "4"
        )

        return {
            "model_name": "demo-classifier",
            "model_version": version,
            "prediction": [0],
        }


def make_deployments():
    """Create a 95/5 stable-canary deployment pair."""

    stable = SimpleNamespace(
        id="stable-v4",
        model_name="demo-classifier",
        model_version="4",
        environment="staging",
        status="staging",
        traffic_percentage=95,
        model_endpoint="http://stable:8000",
    )

    canary = SimpleNamespace(
        id="canary-v5",
        model_name="demo-classifier",
        model_version="5",
        environment="staging",
        status="canary",
        traffic_percentage=5,
        model_endpoint="http://canary:8000",
    )

    return [stable, canary]


def configure_router(
    monkeypatch,
    deployments,
) -> None:
    """Configure the router with fake dependencies."""

    monkeypatch.setattr(
        router_main,
        "AsyncSessionFactory",
        FakeSessionFactory(),
    )

    monkeypatch.setattr(
        router_main,
        "deployment_repository",
        FakeDeploymentRepository(
            deployments
        ),
    )

    monkeypatch.setattr(
        router_main,
        "ModelServerClient",
        FakeModelServerClient,
    )


def test_router_sends_stable_traffic(
    monkeypatch,
) -> None:
    """A bucket inside 95% should select v4."""

    configure_router(
        monkeypatch,
        make_deployments(),
    )

    def choose_stable(deployments):
        return next(
            deployment
            for deployment in deployments
            if deployment.model_version == "4"
        )

    monkeypatch.setattr(
        router_main,
        "select_weighted_deployment",
        choose_stable,
    )

    response = client.post(
        "/predict",
        json={
            "project_id": str(PROJECT_ID),
            "features": [0.0] * 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["model_version"] == "4"


def test_router_sends_canary_traffic(
    monkeypatch,
) -> None:
    """A bucket inside the 5% canary range should select v5."""

    configure_router(
        monkeypatch,
        make_deployments(),
    )

    def choose_canary(deployments):
        return next(
            deployment
            for deployment in deployments
            if deployment.model_version == "5"
        )

    monkeypatch.setattr(
        router_main,
        "select_weighted_deployment",
        choose_canary,
    )

    response = client.post(
        "/predict",
        json={
            "project_id": str(PROJECT_ID),
            "features": [0.0] * 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["model_version"] == "5"


def test_router_preserves_canary_endpoint(
    monkeypatch,
) -> None:
    """The selected deployment's endpoint must be used."""

    deployments = make_deployments()

    configure_router(
        monkeypatch,
        deployments,
    )

    selected = deployments[1]

    monkeypatch.setattr(
        router_main,
        "select_weighted_deployment",
        lambda deployments: selected,
    )

    response = client.post(
        "/predict",
        json={
            "project_id": str(PROJECT_ID),
            "features": [0.0] * 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["model_version"] == "5"


def test_router_rejects_invalid_total_traffic(
    monkeypatch,
) -> None:
    """The router must reject an invalid traffic configuration."""

    deployments = make_deployments()

    deployments[0].traffic_percentage = 90
    deployments[1].traffic_percentage = 20

    configure_router(
        monkeypatch,
        deployments,
    )

    # Use the real selector so its total-traffic validation runs.
    response = client.post(
        "/predict",
        json={
            "project_id": str(PROJECT_ID),
            "features": [0.0] * 10,
        },
    )

    assert response.status_code == 503

    assert (
        "Invalid routing configuration"
        in response.json()["detail"]
    )
