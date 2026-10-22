from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

VALID_FEATURES = [0.0] * 10


def mocked_http_client(
    *,
    status_code: int = 200,
    body: dict | None = None,
):
    """Create a mocked async HTTP client for model-server requests."""

    upstream_response = MagicMock()
    upstream_response.status_code = status_code
    upstream_response.json.return_value = body or {
        "model_name": "demo-classifier",
        "model_version": "5",
        "prediction": [0],
    }

    instance = MagicMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    instance.post = AsyncMock(return_value=upstream_response)

    return instance


def test_create_prediction() -> None:
    """Return the actual model-server response and request latency."""

    mock_client = mocked_http_client()

    with patch(
        "backend.app.api.predictions.httpx.AsyncClient",
        return_value=mock_client,
    ):
        response = client.post(
            "/api/v1/predictions",
            json={"features": VALID_FEATURES},
        )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["model_name"] == "demo-classifier"
    assert data["model_version"] == "5"
    assert data["prediction"] == [0]
    assert data["latency_ms"] >= 0

    mock_client.post.assert_awaited_once()
    assert mock_client.post.await_args.kwargs["json"] == {
        "features": VALID_FEATURES,
    }


def test_prediction_rejects_wrong_feature_count() -> None:
    """Reject feature vectors that do not contain exactly ten values."""

    for features in ([0.0] * 9, [0.0] * 11):
        response = client.post(
            "/api/v1/predictions",
            json={"features": features},
        )
        assert response.status_code == 422


def test_prediction_returns_503_when_model_server_is_unavailable() -> None:
    """Return 503 when the model server cannot be reached."""

    mock_client = mocked_http_client()
    mock_client.post.side_effect = __import__("httpx").ConnectError(
        "Simulated connection failure",
    )

    with patch(
        "backend.app.api.predictions.httpx.AsyncClient",
        return_value=mock_client,
    ):
        response = client.post(
            "/api/v1/predictions",
            json={"features": VALID_FEATURES},
        )

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_prediction_returns_502_for_upstream_error() -> None:
    """Translate unsuccessful model-server responses to HTTP 502."""

    mock_client = mocked_http_client(status_code=500)

    with patch(
        "backend.app.api.predictions.httpx.AsyncClient",
        return_value=mock_client,
    ):
        response = client.post(
            "/api/v1/predictions",
            json={"features": VALID_FEATURES},
        )

    assert response.status_code == 502
    assert "model server" in response.json()["detail"].lower()


def test_prediction_returns_502_for_invalid_upstream_response() -> None:
    """Reject malformed model-server responses."""

    mock_client = mocked_http_client(
        body={"unexpected": "response"},
    )

    with patch(
        "backend.app.api.predictions.httpx.AsyncClient",
        return_value=mock_client,
    ):
        response = client.post(
            "/api/v1/predictions",
            json={"features": VALID_FEATURES},
        )

    assert response.status_code == 502
    assert "invalid response" in response.json()["detail"].lower()
