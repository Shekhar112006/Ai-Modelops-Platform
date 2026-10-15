from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.deployment_recovery_event import (
    DeploymentRecoveryEvent,
)


class DeploymentRecoveryEventRepository:
    """Database operations for deployment failure and recovery events."""

    def create(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        event_type: str,
        severity: str,
        message: str,
        consecutive_failures: int = 0,
        details: dict[str, Any] | None = None,
    ) -> DeploymentRecoveryEvent:
        """Add a recovery event to the current database transaction."""

        event = DeploymentRecoveryEvent(
            deployment_id=deployment_id,
            event_type=event_type,
            severity=severity,
            message=message,
            consecutive_failures=consecutive_failures,
            details=details,
        )

        session.add(event)
        session.flush()

        return event

    def list_by_deployment(
        self,
        session: Session,
        deployment_id: UUID,
        *,
        limit: int = 100,
        event_type: str | None = None,
    ) -> list[DeploymentRecoveryEvent]:
        """Return a deployment's events, newest first."""

        if limit < 1:
            raise ValueError("limit must be at least 1")

        statement = select(
            DeploymentRecoveryEvent
        ).where(
            DeploymentRecoveryEvent.deployment_id == deployment_id
        )

        if event_type is not None:
            statement = statement.where(
                DeploymentRecoveryEvent.event_type == event_type
            )

        statement = statement.order_by(
            DeploymentRecoveryEvent.created_at.desc(),
            DeploymentRecoveryEvent.id.desc(),
        ).limit(limit)

        return list(session.scalars(statement).all())
