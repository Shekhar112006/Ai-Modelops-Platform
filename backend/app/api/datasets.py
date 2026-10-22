from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.schemas.dataset import DatasetPreview, DatasetRead
from backend.app.services.dataset_service import (
    DatasetNotFoundError,
    DatasetService,
    DatasetValidationError,
    ProjectNotFoundError,
)


router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]

dataset_service = DatasetService()


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    project_id: UUID,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
) -> DatasetRead:
    """Upload and register a validated CSV dataset."""

    try:
        dataset = await dataset_service.upload_dataset(
            session=session,
            project_id=project_id,
            upload=file,
            name=name,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return DatasetRead.model_validate(dataset)


@router.get(
    "/projects/{project_id}/datasets",
    response_model=list[DatasetRead],
)
async def list_project_datasets(
    project_id: UUID,
    session: SessionDep,
) -> list[DatasetRead]:
    """List datasets associated with one project."""

    try:
        datasets = await dataset_service.list_project_datasets(
            session=session,
            project_id=project_id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [
        DatasetRead.model_validate(dataset)
        for dataset in datasets
    ]


@router.get(
    "/datasets",
    response_model=list[DatasetRead],
)
async def list_datasets(
    session: SessionDep,
) -> list[DatasetRead]:
    """List datasets across all projects."""

    datasets = await dataset_service.list_datasets(session)

    return [
        DatasetRead.model_validate(dataset)
        for dataset in datasets
    ]


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetRead,
)
async def get_dataset(
    dataset_id: UUID,
    session: SessionDep,
) -> DatasetRead:
    """Return metadata for one dataset."""

    try:
        dataset = await dataset_service.get_dataset(
            session=session,
            dataset_id=dataset_id,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DatasetRead.model_validate(dataset)


@router.get(
    "/datasets/{dataset_id}/preview",
    response_model=DatasetPreview,
)
async def preview_dataset(
    dataset_id: UUID,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> DatasetPreview:
    """Return a bounded preview of a stored CSV dataset."""

    try:
        dataset, rows = await dataset_service.preview_dataset(
            session=session,
            dataset_id=dataset_id,
            limit=limit,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return DatasetPreview(
        dataset_id=dataset.id,
        name=dataset.name,
        columns=dataset.columns,
        row_count=dataset.row_count,
        preview_rows=rows,
        preview_limit=limit,
    )
