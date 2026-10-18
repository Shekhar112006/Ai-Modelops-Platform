from __future__ import annotations

from fastapi.testclient import TestClient

from model_server import main as model_server_main


client = TestClient(model_server_main.app)


class FakeInference:
    """Provide deterministic predictions without loading MLflow artifacts."""

    def predict(self, features: list[float]) -> list[int]:
        """Return a predictable result for a valid feature vector."""
        return [1]


def test_model_server_health(monkeypatch) -> None:
    """The model server reports healthy when inference is available."""

    monkeypatch.setattr(
        model_server_main,
        "inference",
        FakeInference(),
    )

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["model_name"] == "demo-classifier"
    assert data["model_version"] == "4"


def test_prediction(monkeypatch) -> None:
    """A valid ten-feature request returns a prediction."""

    monkeypatch.setattr(
        model_server_main,
        "inference",
        FakeInference(),
    )

    response = client.post(
        "/predict",
        json={"features": [0.0] * 10},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model_name"] == "demo-classifier"
    assert data["model_version"] == "4"
    assert data["prediction"] == [1]


def test_too_few_features() -> None:
    """Requests with fewer than ten features should be rejected."""

    response = client.post(
        "/predict",
        json={"features": [0.0] * 9},
    )

    assert response.status_code == 422


def test_too_many_features() -> None:
    """Requests with more than ten features should be rejected."""

    response = client.post(
        "/predict",
        json={"features": [0.0] * 11},
    )

    assert response.status_code == 422
