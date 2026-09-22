from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.training_job import TrainingJob


class TrainingJobRepository:
    """Database operations for training jobs."""

    async def create(
        self,
        session: AsyncSession,
        job: TrainingJob,
    ) -> TrainingJob:
        """Persist a new training job."""

        session.add(job)
        await session.flush()
        await session.refresh(job)

        return job

    async def get_by_id(
        self,
        session: AsyncSession,
        job_id: UUID,
    ) -> TrainingJob | None:
        """Fetch a training job by ID."""

        result = await session.execute(
            select(TrainingJob).where(
                TrainingJob.id == job_id
            )
        )

        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> list[TrainingJob]:
        """Return training jobs belonging to a project."""

        result = await session.execute(
            select(TrainingJob)
            .where(
                TrainingJob.project_id == project_id
            )
            .order_by(
                TrainingJob.created_at.desc()
            )
        )

        return list(result.scalars().all())

    async def set_task_id(
        self,
        session: AsyncSession,
        job_id: UUID,
        task_id: str,
    ) -> None:
        """Persist the Celery task ID without overwriting job status."""

        await session.execute(
            update(TrainingJob)
            .where(TrainingJob.id == job_id)
            .values(celery_task_id=task_id)
        )