from __future__ import annotations

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Request containing one feature vector for inference."""

    features: list[float] = Field(
        min_length=10,
        max_length=10,
    )


class PredictionResponse(BaseModel):
    """Response containing the model prediction."""

    model_name: str
    model_version: str
    prediction: list[object]
