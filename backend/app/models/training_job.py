from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class TrainingJob(Base):
    """Persistent record of an asynchronous model training job."""

    __tablename__ = "training_jobs"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    workload: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="demo-classification",
        server_default="demo-classification",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )

    celery_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    selected_model_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    selected_model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )