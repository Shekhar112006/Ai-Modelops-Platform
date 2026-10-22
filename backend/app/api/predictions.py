from __future__ import annotations

import logging
from time import perf_counter

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ValidationError

from backend.app.core.config import settings
from backend.app.core.metrics import record_prediction_metric
from backend.app.schemas.prediction import PredictionCreate, PredictionRead

logger = logging.getLogger(__name__)

router = APIRouter()


class ModelServerPrediction(BaseModel):
    """Validated response received from the model server."""

    model_name: str
    model_version: str
    prediction: list[object]


def record_outcome(
    *,
    outcome: str,
    model_name: str = "unknown",
    model_version: str = "unknown",
) -> None:
    """Record prediction outcomes using bounded metric labels."""

    record_prediction_metric(
        service_name="modelops-api",
        environment=settings.environment,
        outcome=outcome,
        model_name=model_name,
        model_version=model_version,
    )


@router.post(
    "/predictions",
    response_model=PredictionRead,
    status_code=status.HTTP_200_OK,
)
async def create_prediction(
    payload: PredictionCreate,
) -> PredictionRead:
    """Forward a validated feature vector to the model server."""

    started = perf_counter()
    endpoint = f"{settings.model_server_url.rstrip('/')}/predict"

    try:
        async with httpx.AsyncClient(
            timeout=settings.prediction_timeout_seconds,
        ) as client:
            response = await client.post(
                endpoint,
                json=payload.model_dump(),
            )

        if not 200 <= response.status_code < 300:
            record_outcome(outcome="upstream_error")
            logger.warning(
                "Model server returned an unsuccessful response",
                extra={
                    "event": "prediction_upstream_error",
                    "upstream_status": response.status_code,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The model server could not complete the prediction.",
            )

        model_result = ModelServerPrediction.model_validate(
            response.json(),
        )

    except HTTPException:
        raise

    except (httpx.TimeoutException, httpx.RequestError) as exc:
        record_outcome(outcome="unavailable")
        logger.warning(
            "Model server request failed",
            extra={"event": "prediction_model_server_unavailable"},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The model server is unavailable. Please try again later.",
        ) from exc

    except (ValueError, ValidationError) as exc:
        record_outcome(outcome="upstream_error")
        logger.exception(
            "Model server returned an invalid prediction response",
            extra={"event": "prediction_invalid_upstream_response"},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model server returned an invalid response.",
        ) from exc

    latency_ms = (perf_counter() - started) * 1000

    record_outcome(
        outcome="success",
        model_name=model_result.model_name,
        model_version=model_result.model_version,
    )

    logger.info(
        "Model prediction completed",
        extra={
            "event": "prediction_completed",
            "model_name": model_result.model_name,
            "model_version": model_result.model_version,
            "latency_ms": round(latency_ms, 2),
        },
    )

    return PredictionRead(
        status="success",
        model_name=model_result.model_name,
        model_version=model_result.model_version,
        prediction=model_result.prediction,
        latency_ms=round(latency_ms, 2),
    )
