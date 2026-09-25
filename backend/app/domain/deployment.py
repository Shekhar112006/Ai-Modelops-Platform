from __future__ import annotations

from enum import StrEnum


class DeploymentEnvironment(StrEnum):
    """Deployment environments supported by the platform."""

    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentStatus(StrEnum):
    """Lifecycle states for a model deployment."""

    CREATED = "created"
    VALIDATING = "validating"
    APPROVED = "approved"
    STAGING = "staging"
    CANARY = "canary"
    PROMOTING = "promoting"
    PRODUCTION = "production"
    ROLLBACK = "rollback"
    ROLLED_BACK = "rolled_back"


ALLOWED_DEPLOYMENT_TRANSITIONS: dict[
    DeploymentStatus,
    frozenset[DeploymentStatus],
] = {
    DeploymentStatus.CREATED: frozenset(
        {DeploymentStatus.VALIDATING}
    ),
    DeploymentStatus.VALIDATING: frozenset(
        {
            DeploymentStatus.APPROVED,
            DeploymentStatus.ROLLBACK,
        }
    ),
    DeploymentStatus.APPROVED: frozenset(
        {
            DeploymentStatus.STAGING,
            DeploymentStatus.ROLLBACK,
        }
    ),
    DeploymentStatus.STAGING: frozenset(
        {
            DeploymentStatus.CANARY,
            DeploymentStatus.ROLLBACK,
        }
    ),
    DeploymentStatus.CANARY: frozenset(
        {
            DeploymentStatus.PROMOTING,
            DeploymentStatus.ROLLBACK,
        }
    ),
    DeploymentStatus.PROMOTING: frozenset(
        {
            DeploymentStatus.PRODUCTION,
            DeploymentStatus.ROLLBACK,
        }
    ),
    DeploymentStatus.PRODUCTION: frozenset(
        {DeploymentStatus.ROLLBACK}
    ),
    DeploymentStatus.ROLLBACK: frozenset(
        {DeploymentStatus.ROLLED_BACK}
    ),
    DeploymentStatus.ROLLED_BACK: frozenset(),
}


class InvalidDeploymentTransition(ValueError):
    """Raised when a deployment attempts an invalid state transition."""


def validate_deployment_transition(
    current: DeploymentStatus,
    target: DeploymentStatus,
) -> None:
    """Validate whether a deployment may move to the target state."""

    allowed_targets = ALLOWED_DEPLOYMENT_TRANSITIONS[current]

    if target not in allowed_targets:
        raise InvalidDeploymentTransition(
            f"Invalid deployment transition: "
            f"{current.value} -> {target.value}."
        )
