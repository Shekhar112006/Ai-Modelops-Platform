from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


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


class DriftDetectionRequest(BaseModel):
    """Batch of observations used for feature drift detection."""

    samples: list[list[float]] = Field(min_length=20)

    @field_validator("samples")
    @classmethod
    def validate_feature_count(
        cls,
        samples: list[list[float]],
    ) -> list[list[float]]:
        if any(len(sample) != 10 for sample in samples):
            raise ValueError(
                "Every sample must contain exactly 10 features."
            )
        return samples


class DriftDetectionResponse(BaseModel):
    """Statistical feature drift report."""

    model_name: str
    model_version: str
    drift_detected: bool
    reference_samples: int
    current_samples: int
    features_checked: int
    drifted_feature_count: int
    drifted_features: list[str]
    significance_level: float
    feature_results: dict[str, dict[str, float | bool]]
