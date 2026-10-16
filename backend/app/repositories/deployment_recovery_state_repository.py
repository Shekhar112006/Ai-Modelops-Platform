"""Persistence operations for automated deployment recovery state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, update
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
                DeploymentRecoveryState.status == "in_progress",
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
                DeploymentRecoveryState.status == "in_progress",
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
