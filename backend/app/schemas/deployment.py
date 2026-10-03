from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.deployment import DeploymentEnvironment


class DeploymentCreate(BaseModel):
    """Request used to create a model deployment."""

    model_name: str = Field(
        min_length=1,
        max_length=255,
    )

    model_version: str = Field(
        min_length=1,
        max_length=100,
    )

    environment: DeploymentEnvironment = Field(
        default=DeploymentEnvironment.STAGING,
    )


class DeploymentRead(BaseModel):
    """API representation of a model deployment."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    project_id: UUID
    model_name: str
    model_version: str
    environment: str
    status: str
    traffic_percentage: int
    model_endpoint: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
