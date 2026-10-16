"""Shared Prometheus metrics for AI ModelOps services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)


HTTP_REQUESTS = Counter(
    "modelops_http_requests",
    "Total HTTP requests handled by ModelOps services.",
    ["service", "method", "path", "status"],
)

HTTP_REQUEST_ERRORS = Counter(
    "modelops_http_request_errors",
    "Total HTTP requests that return an error status.",
    ["service", "method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "modelops_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["service", "method", "path"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

MODEL_PREDICTIONS = Counter(
    "modelops_predictions",
    "Model prediction routing outcomes.",
    [
        "service",
        "environment",
        "model_name",
        "model_version",
        "outcome",
    ],
)


def install_http_metrics(
    app: FastAPI,
    service_name: str,
) -> None:
    """Add HTTP request metrics and a Prometheus scrape endpoint."""

    @app.middleware("http")
    async def record_http_metrics(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Record request count, errors, and processing duration."""

        # Avoid counting Prometheus scrapes as normal application traffic.
        if request.url.path == "/metrics":
            return await call_next(request)

        started = perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            # Use the registered route template, not arbitrary URL paths.
            # This prevents IDs and other path parameters creating
            # unbounded metric label combinations.
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")

            labels = {
                "service": service_name,
                "method": request.method,
                "path": path,
                "status": str(status_code),
            }

            HTTP_REQUESTS.labels(**labels).inc()

            if status_code >= 400:
                HTTP_REQUEST_ERRORS.labels(**labels).inc()

            HTTP_REQUEST_DURATION.labels(
                service=service_name,
                method=request.method,
                path=path,
            ).observe(perf_counter() - started)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        """Expose metrics in Prometheus text exposition format."""

        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )


def record_prediction_metric(
    *,
    service_name: str,
    environment: str,
    outcome: str,
    model_name: str = "unknown",
    model_version: str = "unknown",
) -> None:
    """Record a prediction outcome without high-cardinality identifiers."""

    MODEL_PREDICTIONS.labels(
        service=service_name,
        environment=environment,
        model_name=model_name,
        model_version=model_version,
        outcome=outcome,
    ).inc()
