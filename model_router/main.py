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
    """Route a prediction to the active staging deployment."""

    async with AsyncSessionFactory() as session:
        deployment = (
            await deployment_repository.get_active_by_project(
                session=session,
                project_id=payload.project_id,
                environment="staging",
            )
        )

    if deployment is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No active staging deployment found "
                f"for project '{payload.project_id}'."
            ),
        )

    if not deployment.model_endpoint:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Deployment '{deployment.id}' has no "
                "model serving endpoint."
            ),
        )

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
