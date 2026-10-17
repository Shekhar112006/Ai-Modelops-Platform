"""Local Prometheus exporter for Celery multiprocess metrics."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from wsgiref.simple_server import make_server

from prometheus_client import (
    CollectorRegistry,
    make_wsgi_app,
    multiprocess,
)


logger = logging.getLogger("modelops-worker-metrics")


def create_registry(
    directory: str | Path | None = None,
) -> CollectorRegistry:
    """Create a registry that aggregates Celery worker processes."""

    configured_directory = (
        str(directory)
        if directory is not None
        else os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    )

    if not configured_directory:
        raise RuntimeError(
            "PROMETHEUS_MULTIPROC_DIR must be configured."
        )

    multiprocess_directory = Path(configured_directory)

    if not multiprocess_directory.is_dir():
        raise RuntimeError(
            "Prometheus multiprocess directory does not exist: "
            f"{multiprocess_directory}"
        )

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(
        registry,
        path=str(multiprocess_directory),
    )

    return registry


def main() -> None:
    """Serve aggregated worker metrics on localhost port 8005."""

    logging.basicConfig(level=logging.INFO)

    registry = create_registry()
    metrics_app = make_wsgi_app(registry=registry)

    port = int(os.environ.get("MODELOPS_CELERY_METRICS_PORT", "8005"))

    with make_server("127.0.0.1", port, metrics_app) as server:
        logger.info(
            "Celery metrics exporter started",
            extra={
                "event": "celery_metrics_exporter_started",
                "host": "127.0.0.1",
                "port": port,
            },
        )

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Celery metrics exporter stopped")


if __name__ == "__main__":
    main()
