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


def test_model_server_metrics_record_successful_prediction(monkeypatch) -> None:
    """The metrics endpoint exposes successful inference counts and latency."""

    monkeypatch.setattr(
        model_server_main,
        "inference",
        FakeInference(),
    )

    prediction_response = client.post(
        "/predict",
        json={"features": [0.0] * 10},
    )

    assert prediction_response.status_code == 200

    metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200
    assert "text/plain" in metrics_response.headers["content-type"]
    assert "modelops_model_server_predictions_total" in metrics_response.text
    assert (
        'model_name="demo-classifier",model_version="4",outcome="success"'
        in metrics_response.text
    )
    assert "modelops_model_server_inference_duration_seconds_count" in (
        metrics_response.text
    )


def test_drift_detection_endpoint(monkeypatch) -> None:
    """The model server returns a feature-level drift report."""

    import numpy as np
    import pandas as pd

    from ml.drift.detector import DriftDetector
    from ml.workloads.demo.dataset import FEATURE_COLUMNS

    rng = np.random.default_rng(42)
    reference = pd.DataFrame(
        rng.normal(size=(1000, 10)),
        columns=FEATURE_COLUMNS,
    )
    detector = DriftDetector(reference, FEATURE_COLUMNS)

    monkeypatch.setattr(
        model_server_main,
        "get_drift_detector",
        lambda: detector,
    )

    current = rng.normal(size=(500, 10))
    current[:, 0] += 5.0

    response = client.post(
        "/drift/detect",
        json={"samples": current.tolist()},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["model_name"] == "demo-classifier"
    assert data["drift_detected"] is True
    assert "feature_01" in data["drifted_features"]
    assert data["features_checked"] == 10


def test_drift_detection_rejects_invalid_batch() -> None:
    """The endpoint rejects batches with invalid feature dimensions."""

    response = client.post(
        "/drift/detect",
        json={"samples": [[0.0] * 9 for _ in range(20)]},
    )

    assert response.status_code == 422
