from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from mlflow.exceptions import MlflowException

from backend.app.schemas.registry import (
    ModelVersionRead,
    RegisteredModelRead,
    RegistryModelListRead,
    RegistryVersionListRead,
)
from backend.app.services.registry_service import (
    RegistryModelNotFoundError,
    RegistryService,
    RegistryUnavailableError,
    RegistryVersionNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter()

registry_service = RegistryService()


@router.get(
    "/models",
    response_model=RegistryModelListRead,
)
async def list_registered_models() -> RegistryModelListRead:
    """List registered models and their aliases."""

    try:
        models = registry_service.list_models()

    except RegistryUnavailableError as exc:
        logger.exception("Unable to list registered MLflow models")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except MlflowException as exc:
        logger.exception("MLflow registry request failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The MLflow registry is temporarily unavailable.",
        ) from exc

    return RegistryModelListRead(
        models=[
            RegisteredModelRead.model_validate(model)
            for model in models
        ],
        total=len(models),
    )


@router.get(
    "/models/{model_name}/versions",
    response_model=RegistryVersionListRead,
)
async def list_model_versions(
    model_name: str,
) -> RegistryVersionListRead:
    """List versions of a registered model."""

    try:
        versions = registry_service.list_versions(model_name)

    except RegistryModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except RegistryUnavailableError as exc:
        logger.exception("Unable to list MLflow model versions")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except MlflowException as exc:
        logger.exception("MLflow registry request failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The MLflow registry is temporarily unavailable.",
        ) from exc

    return RegistryVersionListRead(
        model_name=model_name,
        versions=[
            ModelVersionRead.model_validate(version)
            for version in versions
        ],
        total=len(versions),
    )


@router.get(
    "/models/{model_name}/versions/{version}",
    response_model=ModelVersionRead,
)
async def get_model_version(
    model_name: str,
    version: str,
) -> ModelVersionRead:
    """Return details of one registered model version."""

    try:
        model_version = registry_service.get_version(
            model_name=model_name,
            version=version,
        )

    except RegistryVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except RegistryUnavailableError as exc:
        logger.exception("Unable to retrieve MLflow model version")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except MlflowException as exc:
        logger.exception("MLflow registry request failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The MLflow registry is temporarily unavailable.",
        ) from exc

    return ModelVersionRead.model_validate(model_version)
