from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrainingJobCreate(BaseModel):
    """Request used to create a training job."""

    workload: str = Field(
        default="demo-classification",
        min_length=1,
        max_length=120,
    )


class TrainingJobRead(BaseModel):
    """API representation of a training job."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    project_id: UUID
    workload: str
    status: str
    celery_task_id: str | None
    selected_model_name: str | None
    selected_model_version: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None