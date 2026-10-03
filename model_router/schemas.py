from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class RouterPredictionRequest(BaseModel):
    """Request accepted by the model router."""

    project_id: UUID

    features: list[float] = Field(
        min_length=10,
        max_length=10,
    )


class RouterPredictionResponse(BaseModel):
    """Prediction response returned by the model router."""

    model_name: str
    model_version: str
    prediction: list[object]
