from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException

from backend.app.db.session import AsyncSessionFactory
from backend.app.core.logging_config import configure_logging
from backend.app.core.metrics import (
    install_http_metrics,
    record_prediction_metric,
)
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
from platform_version import PLATFORM_VERSION


configure_logging("modelops-model-router")
logger = logging.getLogger(__name__)

deployment_repository = DeploymentRepository()


app = FastAPI(
    title="AI ModelOps Model Router",
    version=PLATFORM_VERSION,
)

install_http_metrics(
    app,
    service_name="modelops-model-router",
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

    started = perf_counter()

    logger.info(
        "Prediction routing started",
        extra={
            "event": "prediction_routing_started",
            "project_id": str(payload.project_id),
            "environment": payload.environment,
        },
    )

    async with AsyncSessionFactory() as session:
            deployments = (
                await deployment_repository.list_routable_by_project(
                    session=session,
                    project_id=payload.project_id,
                    environment=payload.environment,
                )
            )

    if not deployments:
        logger.warning(
            "No active deployment is available for prediction",
            extra={
                "event": "model_router_no_active_deployment",
                "project_id": str(payload.project_id),
                "environment": payload.environment,
            },
        )
        record_prediction_metric(
            service_name="modelops-model-router",
            environment=payload.environment,
            outcome="no_deployment",
        )
        raise HTTPException(
            status_code=404,
            detail=(
                f"No active {payload.environment} deployment found "
                f"for project '{payload.project_id}'."
            ),
        )

    try:
        deployment = select_weighted_deployment(
            deployments
        )

    except NoRoutableDeploymentError as exc:
        logger.warning(
            "No deployment could be selected for prediction",
            extra={
                "event": "model_router_no_routable_deployment",
                "project_id": str(payload.project_id),
                "environment": payload.environment,
                "error": str(exc),
            },
        )
        record_prediction_metric(
            service_name="modelops-model-router",
            environment=payload.environment,
            outcome="routing_error",
        )
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        logger.error(
            "Invalid model routing configuration",
            extra={
                "event": "model_router_invalid_configuration",
                "project_id": str(payload.project_id),
                "environment": payload.environment,
                "error": str(exc),
            },
        )
        record_prediction_metric(
            service_name="modelops-model-router",
            environment=payload.environment,
            outcome="routing_error",
        )
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
        logger.exception(
            "Model server prediction failed",
            extra={
                "event": "model_server_unavailable",
                "deployment_id": str(deployment.id),
                "model_name": deployment.model_name,
                "model_version": deployment.model_version,
                "project_id": str(payload.project_id),
                "environment": payload.environment,
                "error_type": type(exc).__name__,
            },
        )
        record_prediction_metric(
            service_name="modelops-model-router",
            environment=payload.environment,
            outcome="model_server_error",
            model_name=deployment.model_name,
            model_version=deployment.model_version,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Model server unavailable: {exc}",
        ) from exc

    logger.info(
        "Prediction routed successfully",
        extra={
            "event": "prediction_routing_succeeded",
            "project_id": str(payload.project_id),
            "deployment_id": str(deployment.id),
            "environment": payload.environment,
            "model_name": str(result["model_name"]),
            "model_version": str(result["model_version"]),
            "response_time_ms": max(
                0,
                round((perf_counter() - started) * 1000),
            ),
        },
    )

    record_prediction_metric(
        service_name="modelops-model-router",
        environment=payload.environment,
        outcome="success",
        model_name=str(result["model_name"]),
        model_version=str(result["model_version"]),
    )

    return RouterPredictionResponse(
        model_name=str(result["model_name"]),
        model_version=str(result["model_version"]),
        prediction=list(result["prediction"]),
    )
