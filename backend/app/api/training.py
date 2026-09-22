from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.schemas.training_job import (
    TrainingJobCreate,
    TrainingJobRead,
)
from backend.app.services.training_service import (
    ProjectNotFoundError,
    TrainingService,
)


router = APIRouter()

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]

training_service = TrainingService()


@router.post(
    "/projects/{project_id}/training-jobs",
    response_model=TrainingJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_training_job(
    project_id: UUID,
    payload: TrainingJobCreate,
    session: SessionDep,
) -> TrainingJobRead:
    """Queue an asynchronous model training job."""

    try:
        job = await training_service.create_training_job(
            session=session,
            project_id=project_id,
            workload=payload.workload,
        )

    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return TrainingJobRead.model_validate(job)


@router.get(
    "/training-jobs/{job_id}",
    response_model=TrainingJobRead,
)
async def get_training_job(
    job_id: UUID,
    session: SessionDep,
) -> TrainingJobRead:
    """Return the current state of a training job."""

    job = await training_service.training_job_repository.get_by_id(
        session,
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training job '{job_id}' was not found.",
        )

    return TrainingJobRead.model_validate(job)


@router.get(
    "/projects/{project_id}/training-jobs",
    response_model=list[TrainingJobRead],
)
async def list_training_jobs(
    project_id: UUID,
    session: SessionDep,
) -> list[TrainingJobRead]:
    """List training jobs for a project."""

    jobs = await training_service.training_job_repository.list_by_project(
        session,
        project_id,
    )

    return [
        TrainingJobRead.model_validate(job)
        for job in jobs
    ]
