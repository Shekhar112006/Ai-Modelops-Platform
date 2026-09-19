from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.schemas.project import (
    ProjectCreate,
    ProjectRead,
)
from backend.app.services.project_service import (
    ProjectAlreadyExistsError,
    ProjectService,
)


router = APIRouter()

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]

project_service = ProjectService()


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate,
    session: SessionDep,
) -> ProjectRead:
    """Create a new ModelOps project."""

    try:
        project = await project_service.create_project(
            session=session,
            name=payload.name,
            description=payload.description,
        )

    except ProjectAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ProjectRead.model_validate(project)


@router.get(
    "",
    response_model=list[ProjectRead],
)
async def list_projects(
    session: SessionDep,
) -> list[ProjectRead]:
    """Return all ModelOps projects."""

    projects = await project_service.list_projects(session)

    return [
        ProjectRead.model_validate(project)
        for project in projects
    ]