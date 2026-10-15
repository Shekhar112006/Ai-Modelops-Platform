from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.deployment import Deployment
from backend.app.models.deployment_health_check import DeploymentHealthCheck


class DeploymentHealthCheckRepository:
    """Persistence operations for deployment health monitoring."""

    MONITORED_STATUSES = (
        "staging",
        "canary",
        "promoting",
        "production",
    )

    def list_monitorable_deployments(
        self,
        session: Session,
    ) -> list[Deployment]:
        """Return deployed models with configured health endpoints.

        Zero-traffic stable deployments are included because they may
        be needed as rollback targets.
        """

        statement = (
            select(Deployment)
            .where(
                Deployment.status.in_(self.MONITORED_STATUSES),
                Deployment.model_endpoint.is_not(None),
                Deployment.model_endpoint != "",
            )
            .order_by(Deployment.created_at.asc())
        )

        return list(session.scalars(statement).all())

    def get_latest_for_deployment(
        self,
        session: Session,
        deployment_id: UUID,
    ) -> DeploymentHealthCheck | None:
        """Return the latest recorded health check for a deployment."""

        statement = (
            select(DeploymentHealthCheck)
            .where(
                DeploymentHealthCheck.deployment_id == deployment_id
            )
            .order_by(DeploymentHealthCheck.checked_at.desc())
            .limit(1)
        )

        return session.scalars(statement).first()

    def create(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        is_healthy: bool,
        response_time_ms: int | None,
        status_code: int | None,
        consecutive_failures: int,
        error_message: str | None,
    ) -> DeploymentHealthCheck:
        """Add a health-check result to the session."""

        check = DeploymentHealthCheck(
            deployment_id=deployment_id,
            is_healthy=is_healthy,
            response_time_ms=response_time_ms,
            status_code=status_code,
            consecutive_failures=consecutive_failures,
            error_message=error_message,
        )

        session.add(check)
        session.flush()

        return check
