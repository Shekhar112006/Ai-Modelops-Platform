from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class DeploymentRecoveryEvent(Base):
    """Persistent audit event for deployment failures and recovery actions."""

    __tablename__ = "deployment_recovery_events"

    __table_args__ = (
        CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_recovery_events_consecutive_failures_nonnegative",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'error')",
            name="ck_recovery_events_severity",
        ),
        Index(
            "ix_recovery_events_deployment_created_at",
            "deployment_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    deployment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="warning",
        server_default="warning",
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
