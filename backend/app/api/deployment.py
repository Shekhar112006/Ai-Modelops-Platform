from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.domain.deployment import (
    DeploymentEnvironment,
)
from backend.app.schemas.deployment import (
    DeploymentCreate,
    DeploymentRead,
)
from backend.app.services.deployment_service import (
    DeploymentModelNotEligibleError,
    DeploymentModelNotFoundError,
    DeploymentNotFoundError,
    DeploymentProjectNotFoundError,
    DeploymentService,
)


router = APIRouter()

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]

deployment_service = DeploymentService()


@router.post(
    "/projects/{project_id}/deployments",
    response_model=DeploymentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    project_id: UUID,
    payload: DeploymentCreate,
    session: SessionDep,
) -> DeploymentRead:
    """Create a deployment for a validated MLflow model version."""

    try:
        deployment = await deployment_service.create_deployment(
            session=session,
            project_id=project_id,
            model_name=payload.model_name,
            model_version=payload.model_version,
            environment=DeploymentEnvironment(
                payload.environment
            ),
        )

    except DeploymentProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except DeploymentModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except DeploymentModelNotEligibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return DeploymentRead.model_validate(deployment)


@router.get(
    "/deployments/{deployment_id}",
    response_model=DeploymentRead,
)
async def get_deployment(
    deployment_id: UUID,
    session: SessionDep,
) -> DeploymentRead:
    """Return one deployment."""

    try:
        deployment = await deployment_service.get_deployment(
            session,
            deployment_id,
        )

    except DeploymentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DeploymentRead.model_validate(deployment)


@router.get(
    "/projects/{project_id}/deployments",
    response_model=list[DeploymentRead],
)
async def list_project_deployments(
    project_id: UUID,
    session: SessionDep,
) -> list[DeploymentRead]:
    """List deployments belonging to a project."""

    deployments = (
        await deployment_service.list_project_deployments(
            session,
            project_id,
        )
    )

    return [
        DeploymentRead.model_validate(deployment)
        for deployment in deployments
    ]
