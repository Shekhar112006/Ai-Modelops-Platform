from __future__ import annotations

from pydantic import BaseModel, Field


class PredictionCreate(BaseModel):
    """Request body for a single model inference."""

    features: list[float] = Field(
        min_length=10,
        max_length=10,
    )


class PredictionRead(BaseModel):
    """API response containing the model prediction."""

    status: str
    model_name: str
    model_version: str
    prediction: list[object]
    latency_ms: float = Field(ge=0)
