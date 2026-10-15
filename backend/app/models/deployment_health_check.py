from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class DeploymentHealthCheck(Base):
    """Persistent health-check result for a model deployment."""

    __tablename__ = "deployment_health_checks"

    __table_args__ = (
        CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_health_checks_response_time_nonnegative",
        ),
        CheckConstraint(
            "status_code IS NULL OR "
            "(status_code >= 100 AND status_code <= 599)",
            name="ck_health_checks_status_code_valid",
        ),
        CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_health_checks_consecutive_failures_nonnegative",
        ),
        Index(
            "ix_health_checks_deployment_checked_at",
            "deployment_id",
            "checked_at",
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

    is_healthy: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
