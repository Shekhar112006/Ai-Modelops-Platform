from __future__ import annotations

from fastapi import FastAPI, HTTPException

from backend.app.db.session import AsyncSessionFactory
from backend.app.repositories.deployment_repository import (
    DeploymentRepository,
)
from model_router.client import ModelServerClient
from model_router.schemas import (
    RouterPredictionRequest,
    RouterPredictionResponse,
)
from model_router.selector import (
    NoRoutableDeploymentError,
    select_weighted_deployment,
)


deployment_repository = DeploymentRepository()


app = FastAPI(
    title="AI ModelOps Model Router",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Report that the model router process is running."""

    return {
        "status": "healthy",
    }


@app.post(
    "/predict",
    response_model=RouterPredictionResponse,
)
async def predict(
    payload: RouterPredictionRequest,
) -> RouterPredictionResponse:
    """Route a prediction using active deployment traffic weights."""

    async with AsyncSessionFactory() as session:
        deployments = (
            await deployment_repository.list_routable_by_project(
                session=session,
                project_id=payload.project_id,
                environment="staging",
            )
        )

    if not deployments:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No active staging deployment found "
                f"for project '{payload.project_id}'."
            ),
        )

    try:
        deployment = select_weighted_deployment(
            deployments
        )

    except NoRoutableDeploymentError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Invalid routing configuration: {exc}",
        ) from exc

    client = ModelServerClient(
        base_url=deployment.model_endpoint,
    )

    try:
        result = await client.predict(
            payload.features,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model server unavailable: {exc}",
        ) from exc

    return RouterPredictionResponse(
        model_name=str(result["model_name"]),
        model_version=str(result["model_version"]),
        prediction=list(result["prediction"]),
    )
