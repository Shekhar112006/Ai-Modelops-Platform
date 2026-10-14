from __future__ import annotations

from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field


class RouterPredictionRequest(BaseModel):
    project_id: UUID
    environment: Literal["staging", "production"] = "staging"
    features: list[float] = Field(min_length=10, max_length=10)


class RouterPredictionResponse(BaseModel):
    """Prediction response returned by the model router."""

    model_name: str
    model_version: str
    prediction: list[object]
