from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from ml.inference.predict import ModelInference
from model_server.schemas import (
    PredictionRequest,
    PredictionResponse,
)


MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "demo-classifier",
)

MODEL_VERSION = os.getenv(
    "MODEL_VERSION",
    "4",
)


try:
    inference = ModelInference(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
    )
    MODEL_LOAD_ERROR: str | None = None

except Exception as exc:
    inference = None
    MODEL_LOAD_ERROR = str(exc)


app = FastAPI(
    title="AI ModelOps Model Server",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Report model server health and model loading state."""

    if inference is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Model failed to load: "
                f"{MODEL_LOAD_ERROR}"
            ),
        )

    return {
        "status": "healthy",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
    }


@app.post(
    "/predict",
    response_model=PredictionResponse,
)
async def predict(
    payload: PredictionRequest,
) -> PredictionResponse:
    """Generate a prediction from the loaded model."""

    if inference is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Model failed to load: "
                f"{MODEL_LOAD_ERROR}"
            ),
        )

    try:
        prediction = inference.predict(
            payload.features
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return PredictionResponse(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        prediction=prediction,
    )
