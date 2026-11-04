from __future__ import annotations

import logging

import httpx
import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.session import get_session


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Report whether the API process is alive."""

    return {"status": "alive"}


@router.get("/ready")
async def readiness(
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Report whether the API can reach PostgreSQL."""

    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return {"status": "ready"}


@router.get("/services")
async def service_health(
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Report the health of the platform's dependent services."""

    services: dict[str, str] = {
        "api": "healthy",
        "postgresql": "unhealthy",
        "redis": "unhealthy",
        "model_server": "unhealthy",
    }

    # PostgreSQL health check
    try:
        await session.execute(text("SELECT 1"))
        services["postgresql"] = "healthy"
    except SQLAlchemyError:
        logger.warning(
            "PostgreSQL health check failed",
            extra={"event": "health_check_postgresql_failed"},
        )

    # Redis health check
    redis_client = redis.from_url(
        settings.redis_url,
        socket_connect_timeout=settings.health_check_timeout_seconds,
        socket_timeout=settings.health_check_timeout_seconds,
    )

    try:
        await redis_client.ping()
        services["redis"] = "healthy"
    except redis.RedisError:
        logger.warning(
            "Redis health check failed",
            extra={"event": "health_check_redis_failed"},
        )
    finally:
        await redis_client.aclose()

    # Model server health check
    model_server_health_url = (
        f"{settings.model_server_url.rstrip('/')}/health"
    )

    try:
        async with httpx.AsyncClient(
            timeout=settings.health_check_timeout_seconds,
        ) as client:
            response = await client.get(model_server_health_url)

        if response.is_success:
            services["model_server"] = "healthy"

    except (httpx.TimeoutException, httpx.RequestError):
        logger.warning(
            "Model server health check failed",
            extra={"event": "health_check_model_server_failed"},
        )

    overall_status = (
        "healthy"
        if all(value == "healthy" for value in services.values())
        else "degraded"
    )

    return {
        "status": overall_status,
        "services": services,
    }