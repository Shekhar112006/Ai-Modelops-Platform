from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import (
    datasets,
    deployment,
    health,
    projects,
    predictions,
    registry,
    training,
)
from backend.app.core.config import settings
from backend.app.db.session import engine
from backend.app.core.logging_config import configure_logging
from backend.app.core.metrics import install_http_metrics
from platform_version import PLATFORM_VERSION

configure_logging("modelops-api")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application-wide resources."""

    logger.info(
        "API application started",
        extra={
            "event": "api_started",
            "environment": settings.environment,
        },
    )

    try:
        yield
    finally:
        logger.info(
            "API application shutting down",
            extra={"event": "api_shutting_down"},
        )
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=PLATFORM_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

install_http_metrics(app, service_name="modelops-api")

app.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

app.include_router(
    projects.router,
    prefix="/api/v1/projects",
    tags=["projects"],
)

app.include_router(
    training.router,
    prefix="/api/v1",
    tags=["training"],
)

app.include_router(
    predictions.router,
    prefix="/api/v1",
    tags=["predictions"],
)

app.include_router(
    deployment.router,
    prefix="/api/v1",
    tags=["deployments"],
)

app.include_router(
    registry.router,
    prefix="/api/v1/registry",
    tags=["registry"],
)

app.include_router(
    datasets.router,
    prefix="/api/v1",
    tags=["datasets"],
)

@app.get("/")
async def root() -> dict[str, str]:
    """Return basic platform information."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }
