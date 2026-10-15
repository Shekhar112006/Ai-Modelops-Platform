from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryAction(str, Enum):
    """Actions that the recovery policy can recommend."""

    NONE = "none"
    ROLLBACK = "rollback"


@dataclass(frozen=True)
class RecoveryDecision:
    """Immutable result of evaluating a deployment's recovery eligibility."""

    action: RecoveryAction
    reason: str

    @property
    def eligible(self) -> bool:
        """Return whether an automated rollback is approved."""

        return self.action == RecoveryAction.ROLLBACK


class DeploymentRecoveryPolicy:
    """Determine whether an unhealthy deployment qualifies for rollback."""

    RECOVERABLE_STATUSES = frozenset({"canary", "production"})

    def evaluate(
        self,
        *,
        is_healthy: bool,
        deployment_status: str,
        consecutive_failures: int,
        previous_consecutive_failures: int,
        failure_threshold: int,
    ) -> RecoveryDecision:
        """Evaluate a health result without executing recovery."""

        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")

        if consecutive_failures < 0:
            raise ValueError("consecutive_failures cannot be negative")

        if previous_consecutive_failures < 0:
            raise ValueError(
                "previous_consecutive_failures cannot be negative"
            )

        if is_healthy:
            return RecoveryDecision(
                action=RecoveryAction.NONE,
                reason="deployment_healthy",
            )

        if deployment_status not in self.RECOVERABLE_STATUSES:
            return RecoveryDecision(
                action=RecoveryAction.NONE,
                reason="deployment_status_not_recoverable",
            )

        if previous_consecutive_failures >= failure_threshold:
            return RecoveryDecision(
                action=RecoveryAction.NONE,
                reason="threshold_already_processed",
            )

        if consecutive_failures < failure_threshold:
            return RecoveryDecision(
                action=RecoveryAction.NONE,
                reason="failure_threshold_not_reached",
            )

        return RecoveryDecision(
            action=RecoveryAction.ROLLBACK,
            reason="failure_threshold_reached",
        )
