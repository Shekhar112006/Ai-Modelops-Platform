from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActivityRead(BaseModel):
    """API representation of a recent platform activity."""

    id: UUID
    event_type: str
    title: str
    description: str
    status: str
    project_name: str
    timestamp: datetime
