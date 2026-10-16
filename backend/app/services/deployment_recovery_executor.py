from __future__ import annotations

import asyncio
from uuid import UUID

from backend.app.db.session import AsyncSessionFactory
from backend.app.services.deployment_service import (
    DeploymentNotFoundError,
    DeploymentService,
)


async def _execute_rollback(
    deployment_id: UUID,
) -> dict[str, str]:
    """Execute rollback and return details of the restored stable deployment."""

    async with AsyncSessionFactory() as session:
        service = DeploymentService()
        repository = service.deployment_repository

        deployment = await repository.get_by_id(
            session,
            deployment_id,
        )

        if deployment is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' was not found."
            )

        original_status = deployment.status
        project_deployments = await repository.list_by_project(
            session,
            deployment.project_id,
        )

        # Identify the target before rollback changes deployment state.
        if original_status == "canary":
            stable_candidates = [
                item
                for item in project_deployments
                if item.id != deployment.id
                and item.environment == deployment.environment
                and item.status in {"staging", "production"}
                and item.traffic_percentage > 0
                and bool(item.model_endpoint)
            ]

        elif original_status == "production":
            stable_candidates = [
                item
                for item in project_deployments
                if item.id != deployment.id
                and item.environment == "staging"
                and item.status == "staging"
                and item.traffic_percentage == 0
                and bool(item.model_endpoint)
            ]

        else:
            raise ValueError(
                "Automated rollback requires a canary or production "
                f"deployment; current status is {original_status!r}."
            )

        if len(stable_candidates) != 1:
            raise ValueError(
                "Rollback requires exactly one identifiable stable "
                f"deployment. Found {len(stable_candidates)} candidates."
            )

        expected_restored_id = stable_candidates[0].id

        try:
            rolled_back = await service.rollback_canary_deployment(
                session,
                deployment_id,
            )

            restored = await repository.get_by_id(
                session,
                expected_restored_id,
            )

            if restored is None:
                raise DeploymentNotFoundError(
                    "The rollback target disappeared after rollback."
                )

            # Refresh persisted state after the rollback transaction.
            await session.refresh(restored)

            if restored.traffic_percentage != 100:
                raise ValueError(
                    "The restored deployment does not have 100% traffic. "
                    f"Current traffic is {restored.traffic_percentage}%."
                )

            if not restored.model_endpoint:
                raise ValueError(
                    "The restored deployment has no model endpoint."
                )

        except Exception:
            await session.rollback()
            raise

        return {
            "deployment_id": str(rolled_back.id),
            "status": rolled_back.status,
            "restored_deployment_id": str(restored.id),
            "restored_model_name": restored.model_name,
            "restored_model_version": restored.model_version,
            "restored_model_endpoint": restored.model_endpoint,
            "restored_environment": restored.environment,
            "restored_status": restored.status,
            "restored_traffic_percentage": str(
                restored.traffic_percentage
            ),
        }


def execute_automated_rollback(
    deployment_id: UUID,
) -> dict[str, str]:
    """Run asynchronous rollback from a synchronous Celery worker."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            _execute_rollback(deployment_id)
        )

    raise RuntimeError(
        "Automated rollback must be invoked outside an active event loop."
    )
