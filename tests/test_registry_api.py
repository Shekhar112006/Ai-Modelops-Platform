from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException

from backend.app.main import app
from backend.app.services.registry_service import (
    RegistryModelNotFoundError,
    RegistryUnavailableError,
    RegistryVersionNotFoundError,
)


client = TestClient(app)


def sample_version(version: str = "8") -> dict:
    """Return a representative registered model version."""

    return {
        "name": "demo-classifier",
        "version": version,
        "status": "READY",
        "run_id": "test-run-id",
        "source": "models:/test-model-id",
        "description": None,
        "tags": {
            "validation_status": "passed",
            "lifecycle_status": "candidate",
        },
        "creation_timestamp": 1000,
        "last_updated_timestamp": 1000,
    }


def test_list_registered_models() -> None:
    """Return registered models and their aliases."""

    with patch(
        "backend.app.api.registry.registry_service.list_models",
        return_value=[
            {
                "name": "demo-classifier",
                "description": "",
                "tags": {},
                "aliases": {"candidate": "8"},
                "latest_versions": [sample_version()],
            }
        ],
    ):
        response = client.get("/api/v1/registry/models")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["models"][0]["name"] == "demo-classifier"
    assert data["models"][0]["aliases"]["candidate"] == "8"
    assert data["models"][0]["latest_versions"][0]["version"] == "8"


def test_list_model_versions() -> None:
    """Return model versions in descending version order."""

    with patch(
        "backend.app.api.registry.registry_service.list_versions",
        return_value=[sample_version("8"), sample_version("7")],
    ):
        response = client.get(
            "/api/v1/registry/models/demo-classifier/versions"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["model_name"] == "demo-classifier"
    assert data["total"] == 2
    assert [item["version"] for item in data["versions"]] == ["8", "7"]


def test_get_model_version() -> None:
    """Return details for a specific model version."""

    with patch(
        "backend.app.api.registry.registry_service.get_version",
        return_value=sample_version("8"),
    ):
        response = client.get(
            "/api/v1/registry/models/demo-classifier/versions/8"
        )

    assert response.status_code == 200
    assert response.json()["version"] == "8"
    assert response.json()["status"] == "READY"


def test_missing_model_returns_404() -> None:
    """Return 404 when the requested registered model does not exist."""

    with patch(
        "backend.app.api.registry.registry_service.list_versions",
        side_effect=RegistryModelNotFoundError(
            "Registered model 'missing-model' was not found."
        ),
    ):
        response = client.get(
            "/api/v1/registry/models/missing-model/versions"
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_missing_version_returns_404() -> None:
    """Return 404 when the requested model version does not exist."""

    with patch(
        "backend.app.api.registry.registry_service.get_version",
        side_effect=RegistryVersionNotFoundError(
            "Model 'demo-classifier' version '999999' was not found."
        ),
    ):
        response = client.get(
            "/api/v1/registry/models/demo-classifier/versions/999999"
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_registry_unavailable_returns_503() -> None:
    """Return 503 when MLflow is unavailable."""

    with patch(
        "backend.app.api.registry.registry_service.list_models",
        side_effect=RegistryUnavailableError(
            "Unable to retrieve registered models from MLflow."
        ),
    ):
        response = client.get("/api/v1/registry/models")

    assert response.status_code == 503
    assert response.json()["detail"] == (
    "Unable to retrieve registered models from MLflow."
        )


def test_mlflow_exception_returns_503() -> None:
    """Convert an unexpected MLflow API exception to HTTP 503."""

    with patch(
        "backend.app.api.registry.registry_service.list_models",
        side_effect=MlflowException("Simulated MLflow failure"),
    ):
        response = client.get("/api/v1/registry/models")

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
