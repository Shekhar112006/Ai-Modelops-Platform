from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.repositories.project_repository import ProjectRepository
from backend.app.repositories.training_job_repository import (
    TrainingJobRepository,
)
from backend.app.repositories.deployment_repository import (
    DeploymentRepository,
)
from backend.app.schemas.activity import ActivityRead
from backend.app.services.dataset_service import DatasetService


class ActivityService:
    """Combine platform records into a chronological activity feed."""

    def __init__(
        self,
        project_repository: ProjectRepository | None = None,
        training_job_repository: TrainingJobRepository | None = None,
        deployment_repository: DeploymentRepository | None = None,
        dataset_service: DatasetService | None = None,
    ) -> None:
        self.project_repository = (
            project_repository or ProjectRepository()
        )

        self.training_job_repository = (
            training_job_repository or TrainingJobRepository()
        )

        self.deployment_repository = (
            deployment_repository or DeploymentRepository()
        )

        self.dataset_service = (
            dataset_service or DatasetService()
        )

    async def get_recent_activities(
        self,
        session: AsyncSession,
        limit: int = 10,
    ) -> list[ActivityRead]:
        """Return recent events across all platform projects."""

        projects = await self.project_repository.list(session)

        project_names = {
            project.id: project.name
            for project in projects
        }

        datasets = await self.dataset_service.list_datasets(
            session,
            limit=limit,
        )

        training_jobs = (
            await self.training_job_repository.list_recent(
                session,
                limit=limit,
            )
        )

        deployments = (
            await self.deployment_repository.list_recent(
                session,
                limit=limit,
            )
        )

        activities: list[ActivityRead] = []

        for project in projects[:limit]:
            activities.append(
                ActivityRead(
                    id=project.id,
                    event_type="project",
                    title="Project created",
                    description=f"Project '{project.name}' was created.",
                    status=project.status,
                    project_name=project.name,
                    timestamp=project.created_at,
                )
            )

        for dataset in datasets:
            project_name = project_names.get(
                dataset.project_id,
                "Unknown project",
            )

            activities.append(
                ActivityRead(
                    id=dataset.id,
                    event_type="dataset",
                    title="Dataset uploaded",
                    description=(
                        f"Dataset '{dataset.name}' was added "
                        f"to {project_name}."
                    ),
                    status=dataset.status,
                    project_name=project_name,
                    timestamp=dataset.created_at,
                )
            )

        for job in training_jobs:
            project_name = project_names.get(
                job.project_id,
                "Unknown project",
            )

            timestamp = (
                job.completed_at
                or job.started_at
                or job.created_at
            )

            activities.append(
                ActivityRead(
                    id=job.id,
                    event_type="training",
                    title=f"Training {job.status}",
                    description=(
                        f"{job.workload} training for {project_name}."
                    ),
                    status=job.status,
                    project_name=project_name,
                    timestamp=timestamp,
                )
            )

        for deployment in deployments:
            project_name = project_names.get(
                deployment.project_id,
                "Unknown project",
            )

            timestamp = (
                deployment.completed_at
                or deployment.started_at
                or deployment.created_at
            )

            activities.append(
                ActivityRead(
                    id=deployment.id,
                    event_type="deployment",
                    title=f"Deployment {deployment.status}",
                    description=(
                        f"{deployment.model_name} "
                        f"version {deployment.model_version} "
                        f"to {deployment.environment} for {project_name}."
                    ),
                    status=deployment.status,
                    project_name=project_name,
                    timestamp=timestamp,
                )
            )

        activities.sort(
            key=lambda activity: activity.timestamp,
            reverse=True,
        )

        return activities[:limit]
