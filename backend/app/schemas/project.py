from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Request body used to create a project."""

    name: str = Field(
        min_length=1,
        max_length=120,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )


class ProjectRead(BaseModel):
    """API representation of a project."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime