from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api import health, projects
from backend.app.core.config import settings
from backend.app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application-wide resources."""

    yield

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


@app.get("/")
async def root() -> dict[str, str]:
    """Return basic platform information."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }