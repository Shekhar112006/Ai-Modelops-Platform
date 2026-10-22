from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelVersionRead(BaseModel):
    """API representation of a registered model version."""

    model_config = ConfigDict(extra="ignore")

    name: str
    version: str
    status: str
    run_id: str | None = None
    source: str | None = None
    description: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    creation_timestamp: int | None = None
    last_updated_timestamp: int | None = None


class RegisteredModelRead(BaseModel):
    """API representation of a registered MLflow model."""

    name: str
    description: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    aliases: dict[str, str] = Field(default_factory=dict)
    latest_versions: list[ModelVersionRead] = Field(
        default_factory=list,
    )


class RegistryVersionListRead(BaseModel):
    """Response containing all versions of a registered model."""

    model_name: str
    versions: list[ModelVersionRead]
    total: int


class RegistryModelListRead(BaseModel):
    """Response containing registered models."""

    models: list[RegisteredModelRead]
    total: int
