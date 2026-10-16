from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api import (health, projects, training, deployment,)
from backend.app.core.config import settings
from backend.app.db.session import engine
from backend.app.core.logging_config import configure_logging

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
    version="0.1.0",
    lifespan=lifespan,
)

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
    deployment.router,
    prefix="/api/v1",
    tags=["deployments"],
)

@app.get("/")
async def root() -> dict[str, str]:
    """Return basic platform information."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }