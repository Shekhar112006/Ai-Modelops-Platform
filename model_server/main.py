from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from time import perf_counter

import pandas as pd

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from ml.inference.predict import ModelInference
from model_server.schemas import (
    DriftDetectionRequest,
    DriftDetectionResponse,
    PredictionRequest,
    PredictionResponse,
)
from ml.drift.detector import DriftDetector
from ml.workloads.demo.dataset import FEATURE_COLUMNS
from platform_version import PLATFORM_VERSION


MODEL_NAME = os.getenv("MODEL_NAME", "demo-classifier")
MODEL_VERSION = os.getenv("MODEL_VERSION", "4")

MODEL_SERVER_PREDICTIONS = Counter(
    "modelops_model_server_predictions",
    "Model server inference outcomes.",
    ["model_name", "model_version", "outcome"],
)

MODEL_SERVER_DRIFT_CHECKS = Counter(
    "modelops_model_server_drift_checks",
    "Model server data drift detection requests.",
    ["model_name", "model_version", "outcome"],
)

MODEL_SERVER_DRIFTED_FEATURES = Histogram(
    "modelops_model_server_drifted_features",
    "Number of features flagged by each drift check.",
    ["model_name", "model_version"],
    buckets=(0, 1, 2, 3, 5, 8, 10),
)

MODEL_SERVER_INFERENCE_DURATION = Histogram(
    "modelops_model_server_inference_duration_seconds",
    "Model server inference duration in seconds.",
    ["model_name", "model_version"],
    buckets=(
        0.001, 0.005, 0.01, 0.025, 0.05,
        0.1, 0.25, 0.5, 1.0, 2.5, 5.0,
    ),
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
    version=PLATFORM_VERSION,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Report model server health and model loading state."""

    if inference is None:
        raise HTTPException(
            status_code=503,
            detail=f"Model failed to load: {MODEL_LOAD_ERROR}",
        )

    return {
        "status": "healthy",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
    }


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose model server Prometheus metrics."""

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post(
    "/predict",
    response_model=PredictionResponse,
)
async def predict(
    payload: PredictionRequest,
) -> PredictionResponse:
    """Generate a prediction and record inference metrics."""

    started = perf_counter()
    outcome = "inference_error"

    try:
        if inference is None:
            outcome = "model_unavailable"
            raise HTTPException(
                status_code=503,
                detail=f"Model failed to load: {MODEL_LOAD_ERROR}",
            )

        try:
            prediction = inference.predict(payload.features)

        except ValueError as exc:
            outcome = "invalid_input"
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        outcome = "success"

        return PredictionResponse(
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            prediction=prediction,
        )

    finally:
        MODEL_SERVER_PREDICTIONS.labels(
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            outcome=outcome,
        ).inc()

        MODEL_SERVER_INFERENCE_DURATION.labels(
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
        ).observe(perf_counter() - started)



@lru_cache(maxsize=1)
def get_drift_detector() -> DriftDetector:
    """Load the model training reference dataset once per server process."""

    project_root = Path(__file__).resolve().parents[1]
    reference_path = (
        project_root / "ml" / "data" / "raw" / "demo_dataset.csv"
    )

    if not reference_path.is_file():
        raise FileNotFoundError(
            f"Drift reference dataset not found: {reference_path}"
        )

    reference_data = pd.read_csv(reference_path)

    return DriftDetector(
        reference_data=reference_data,
        feature_columns=FEATURE_COLUMNS,
        significance_level=0.05,
        minimum_samples=20,
    )


@app.post(
    "/drift/detect",
    response_model=DriftDetectionResponse,
)
async def detect_drift(
    payload: DriftDetectionRequest,
) -> DriftDetectionResponse:
    """Compare an observation batch with the training reference data."""

    outcome = "error"

    try:
        report = get_drift_detector().detect(payload.samples)
        outcome = "drift_detected" if report["drift_detected"] else "no_drift"

        MODEL_SERVER_DRIFTED_FEATURES.labels(
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
        ).observe(report["drifted_feature_count"])

        return DriftDetectionResponse(
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            **report,
        )

    finally:
        MODEL_SERVER_DRIFT_CHECKS.labels(
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            outcome=outcome,
        ).inc()
