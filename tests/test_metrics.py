from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app as api_app
from model_router.main import app as router_app


api_client = TestClient(api_app)
router_client = TestClient(router_app)


def test_api_metrics_endpoint_exposes_http_metrics() -> None:
    """The control plane exposes HTTP request counts and durations."""

    response = api_client.get("/")
    assert response.status_code == 200

    metrics_response = api_client.get("/metrics")

    assert metrics_response.status_code == 200

    body = metrics_response.text

    assert "modelops_http_requests_total" in body
    assert "modelops_http_request_duration_seconds" in body
    assert 'service="modelops-api"' in body
    assert 'path="/"' in body


def test_router_metrics_endpoint_exposes_http_metrics() -> None:
    """The Model Router exposes its own HTTP request metrics."""

    response = router_client.get("/health")
    assert response.status_code == 200

    metrics_response = router_client.get("/metrics")

    assert metrics_response.status_code == 200

    body = metrics_response.text

    assert "modelops_http_requests_total" in body
    assert "modelops_http_request_duration_seconds" in body
    assert 'service="modelops-model-router"' in body
    assert 'path="/health"' in body


def test_http_error_counter_records_404_responses() -> None:
    """Unmatched routes count as HTTP errors without exposing raw paths."""

    response = api_client.get("/metrics-test-route-that-does-not-exist")

    assert response.status_code == 404

    metrics_response = api_client.get("/metrics")
    body = metrics_response.text

    assert "modelops_http_request_errors_total" in body
    assert 'service="modelops-api"' in body
    assert 'status="404"' in body
    assert 'path="unmatched"' in body


def test_metrics_scrapes_are_not_counted_as_application_requests() -> None:
    """Scraping metrics does not inflate normal HTTP request counts."""

    response = api_client.get("/metrics")

    assert response.status_code == 200
    assert 'path="/metrics"' not in response.text
