from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.training_job import TrainingJob
from backend.app.repositories.project_repository import (
    ProjectRepository,
)
from backend.app.repositories.training_job_repository import (
    TrainingJobRepository,
)
from worker.tasks import run_training_job


class ProjectNotFoundError(Exception):
    """Raised when a requested project does not exist."""


class TrainingService:
    """Business logic for asynchronous model training."""

    def __init__(
        self,
        project_repository: ProjectRepository | None = None,
        training_job_repository: TrainingJobRepository | None = None,
    ) -> None:
        self.project_repository = (
            project_repository
            or ProjectRepository()
        )

        self.training_job_repository = (
            training_job_repository
            or TrainingJobRepository()
        )

    async def create_training_job(
        self,
        session: AsyncSession,
        project_id: UUID,
        workload: str,
    ) -> TrainingJob:
        """Create a queued job and dispatch it to Celery."""

        project = await self.project_repository.get_by_id(
            session,
            project_id,
        )

        if project is None:
            raise ProjectNotFoundError(
                f"Project '{project_id}' was not found."
            )

        job = TrainingJob(
            project_id=project_id,
            workload=workload,
            status="queued",
        )

        await self.training_job_repository.create(
            session,
            job,
        )

        await session.commit()
        await session.refresh(job)

        try:
            task = run_training_job.delay(
                str(job.id)
            )

        except Exception as exc:
            job.status = "failed"
            job.error_message = (
                f"Failed to queue training job: {exc}"
            )

            await session.commit()
            await session.refresh(job)

            raise

        await self.training_job_repository.set_task_id(
            session=session,
            job_id=job.id,
            task_id=task.id,
        )

        await session.commit()
        await session.refresh(job)

        return job