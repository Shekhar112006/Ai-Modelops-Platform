"""Persistence operations for automated deployment recovery state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app.models.deployment_recovery_state import (
    DeploymentRecoveryState,
)


class DeploymentRecoveryStateRepository:
    """Manage recovery claims and their final outcomes."""

    def claim(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        consecutive_failures: int,
    ) -> bool:
        """Atomically claim a deployment for one recovery attempt.

        A claim succeeds when the state row does not exist or its status
        is idle. Existing in-progress, completed, or failed states cannot
        be claimed again until a healthy check resets the state.
        """
        insert_statement = pg_insert(DeploymentRecoveryState).values(
            deployment_id=deployment_id,
            status="in_progress",
            consecutive_failures=consecutive_failures,
            claimed_at=func.now(),
            completed_at=None,
            last_error=None,
            updated_at=func.now(),
        )

        statement = (
            insert_statement.on_conflict_do_update(
                index_elements=[
                    DeploymentRecoveryState.deployment_id,
                ],
                set_={
                    "status": "in_progress",
                    "consecutive_failures": (
                        insert_statement.excluded.consecutive_failures
                    ),
                    "claimed_at": func.now(),
                    "completed_at": None,
                    "last_error": None,
                    "updated_at": func.now(),
                },
                where=DeploymentRecoveryState.status == "idle",
            )
            .returning(DeploymentRecoveryState.id)
        )

        result = session.execute(statement)
        return result.scalar_one_or_none() is not None

    def reset_after_healthy(
        self,
        session: Session,
        *,
        deployment_id: UUID,
    ) -> bool:
        """Reset an existing recovery state after a healthy check.

        An in-progress recovery cannot be cleared by a health-check task.
        """
        statement = (
            update(DeploymentRecoveryState)
            .where(
                DeploymentRecoveryState.deployment_id == deployment_id,
                DeploymentRecoveryState.status != "in_progress",
                or_(
                    DeploymentRecoveryState.last_error.is_(None),
                    ~DeploymentRecoveryState.last_error.like(
                        "Stale recovery claim detected:%"
                    ),
                ),
            )
            .values(
                status="idle",
                consecutive_failures=0,
                claimed_at=None,
                completed_at=None,
                last_error=None,
                updated_at=func.now(),
            )
        )

        result = session.execute(statement)
        return result.rowcount == 1

    def list_stale_candidate_ids(
        self,
        session: Session,
        *,
        timeout_seconds: float,
    ) -> list[UUID]:
        """List expired recovery claims independently of deployment status."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")

        stale_before = datetime.now(timezone.utc) - timedelta(
            seconds=timeout_seconds
        )

        statement = select(
            DeploymentRecoveryState.deployment_id
        ).where(
            DeploymentRecoveryState.status == "in_progress",
            DeploymentRecoveryState.claimed_at.is_not(None),
            DeploymentRecoveryState.claimed_at <= stale_before,
        )

        return list(session.scalars(statement).all())

    def mark_stale_failed(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        timeout_seconds: float,
    ) -> bool:
        """Mark an expired claim failed without releasing it for retry.

        The update is conditional and atomic. A claim can be marked stale
        only if it is still in progress and its claimed_at timestamp is
        older than the configured timeout. It is deliberately not reset
        to idle, because the original worker may still be executing.
        """
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")

        stale_before = datetime.now(timezone.utc) - timedelta(
            seconds=timeout_seconds
        )
        error = (
            f"Stale recovery claim detected: exceeded {timeout_seconds:g} seconds; "
            "automatic retry was suppressed pending reconciliation."
        )

        statement = (
            update(DeploymentRecoveryState)
            .where(
                DeploymentRecoveryState.deployment_id == deployment_id,
                DeploymentRecoveryState.status == "in_progress",
                DeploymentRecoveryState.claimed_at.is_not(None),
                DeploymentRecoveryState.claimed_at <= stale_before,
            )
            .values(
                status="failed",
                completed_at=func.now(),
                last_error=error,
                updated_at=func.now(),
            )
            .returning(DeploymentRecoveryState.id)
        )

        result = session.execute(statement)
        return result.scalar_one_or_none() is not None

    def mark_completed(
        self,
        session: Session,
        *,
        deployment_id: UUID,
    ) -> bool:
        """Mark a claimed recovery attempt as completed."""
        statement = (
            update(DeploymentRecoveryState)
            .where(
                DeploymentRecoveryState.deployment_id == deployment_id,
                or_(
                    DeploymentRecoveryState.status == "in_progress",
                    and_(
                        DeploymentRecoveryState.status == "failed",
                        DeploymentRecoveryState.last_error.like(
                            "Stale recovery claim detected:%"
                        ),
                    ),
                ),
            )
            .values(
                status="completed",
                completed_at=func.now(),
                last_error=None,
                updated_at=func.now(),
            )
        )

        result = session.execute(statement)
        return result.rowcount == 1

    def mark_failed(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        error: str,
    ) -> bool:
        """Persist the failure of a claimed recovery attempt."""
        statement = (
            update(DeploymentRecoveryState)
            .where(
                DeploymentRecoveryState.deployment_id == deployment_id,
                or_(
                    DeploymentRecoveryState.status == "in_progress",
                    and_(
                        DeploymentRecoveryState.status == "failed",
                        DeploymentRecoveryState.last_error.like(
                            "Stale recovery claim detected:%"
                        ),
                    ),
                ),
            )
            .values(
                status="failed",
                completed_at=func.now(),
                last_error=error,
                updated_at=func.now(),
            )
        )

        result = session.execute(statement)
        return result.rowcount == 1
