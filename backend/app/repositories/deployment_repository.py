from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.deployment import Deployment


class DeploymentRepository:
    """Database operations for model deployments."""

    async def create(
        self,
        session: AsyncSession,
        deployment: Deployment,
    ) -> Deployment:
        """Persist a new deployment and return the refreshed entity."""

        session.add(deployment)

        await session.flush()
        await session.refresh(deployment)

        return deployment

    async def get_by_id(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> Deployment | None:
        """Fetch a deployment by its ID."""

        result = await session.execute(
            select(Deployment).where(
                Deployment.id == deployment_id
            )
        )

        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> list[Deployment]:
        """Return deployments belonging to a project."""

        result = await session.execute(
            select(Deployment)
            .where(
                Deployment.project_id == project_id
            )
            .order_by(
                Deployment.created_at.desc()
            )
        )

        return list(result.scalars().all())

    async def get_active_by_project(
        self,
        session: AsyncSession,
        project_id: UUID,
        environment: str,
    ) -> Deployment | None:
        """Fetch the active production/staging deployment for an environment."""

        result = await session.execute(
            select(Deployment)
            .where(
                Deployment.project_id == project_id,
                Deployment.environment == environment,
                Deployment.status.in_(
                    [
                        "staging",
                        "canary",
                        "promoting",
                        "production",
                    ]
                ),
            )
            .order_by(
                Deployment.created_at.desc()
            )
            .limit(1)
        )

        return result.scalar_one_or_none()

    async def update_status(
        self,
        session: AsyncSession,
        deployment_id: UUID,
        status: str,
    ) -> None:
        """Update a deployment status."""

        await session.execute(
            update(Deployment)
            .where(
                Deployment.id == deployment_id
            )
            .values(status=status)
        )

    async def update_endpoint(
        self,
        session: AsyncSession,
        deployment_id: UUID,
        endpoint: str,
        traffic_percentage: int,
    ) -> None:
        """Set the serving endpoint and traffic allocation."""

        await session.execute(
            update(Deployment)
            .where(
                Deployment.id == deployment_id
            )
            .values(
                model_endpoint=endpoint,
                traffic_percentage=traffic_percentage,
            )
        )
