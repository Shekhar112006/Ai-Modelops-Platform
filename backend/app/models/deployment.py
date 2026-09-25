from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class Deployment(Base):
    """Persistent record of a model deployment."""

    __tablename__ = "deployments"

    __table_args__ = (
        CheckConstraint(
            "traffic_percentage >= 0 AND traffic_percentage <= 100",
            name="ck_deployments_traffic_percentage",
        ),
    )

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

    model_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    environment: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="staging",
        server_default="staging",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="created",
        server_default="created",
        index=True,
    )

    traffic_percentage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    model_endpoint: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
