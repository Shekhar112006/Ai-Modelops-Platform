from __future__ import annotations

from fastapi.testclient import TestClient

from model_server.main import app


client = TestClient(app)


def test_model_server_health() -> None:
    """The model server should report a healthy loaded model."""

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["model_name"] == "demo-classifier"
    assert data["model_version"] == "4"


def test_prediction() -> None:
    """A valid ten-feature request should return a prediction."""

    response = client.post(
        "/predict",
        json={
            "features": [0.0] * 10,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model_name"] == "demo-classifier"
    assert data["model_version"] == "4"
    assert len(data["prediction"]) == 1


def test_too_few_features() -> None:
    """Requests with fewer than ten features should be rejected."""

    response = client.post(
        "/predict",
        json={
            "features": [0.0] * 9,
        },
    )

    assert response.status_code == 422


def test_too_many_features() -> None:
    """Requests with more than ten features should be rejected."""

    response = client.post(
        "/predict",
        json={
            "features": [0.0] * 11,
        },
    )

    assert response.status_code == 422
