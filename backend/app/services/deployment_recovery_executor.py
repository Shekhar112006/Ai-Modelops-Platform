from __future__ import annotations

import asyncio
from uuid import UUID

from backend.app.db.session import AsyncSessionFactory
from backend.app.services.deployment_service import DeploymentService


async def _execute_rollback(
    deployment_id: UUID,
) -> dict[str, str]:
    """Execute rollback using the existing deployment lifecycle service."""

    async with AsyncSessionFactory() as session:
        service = DeploymentService()

        try:
            rolled_back = await service.rollback_canary_deployment(
                session,
                deployment_id,
            )
        except Exception:
            await session.rollback()
            raise

        return {
            "deployment_id": str(rolled_back.id),
            "status": rolled_back.status,
        }


def execute_automated_rollback(
    deployment_id: UUID,
) -> dict[str, str]:
    """Run the asynchronous rollback service from a synchronous worker."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_execute_rollback(deployment_id))

    raise RuntimeError(
        "Automated rollback must be invoked outside an active event loop."
    )
