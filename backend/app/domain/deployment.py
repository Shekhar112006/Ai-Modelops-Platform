from __future__ import annotations

from dataclasses import dataclass
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
            DeploymentStatus.PRODUCTION,
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

def validate_canary_traffic(
    traffic_percentage: int,
) -> None:
    """Validate the traffic percentage for a canary deployment."""

    if not 1 <= traffic_percentage <= 99:
        raise ValueError(
            "Canary traffic percentage must be between "
            "1 and 99."
        )




@dataclass(frozen=True)
class TrafficAllocation:
    """Traffic split between a stable deployment and a canary."""

    stable_percentage: int
    canary_percentage: int

    def __post_init__(self) -> None:
        """Validate the complete traffic allocation."""

        if not 0 <= self.stable_percentage <= 100:
            raise ValueError(
                "Stable traffic percentage must be between "
                "0 and 100."
            )

        if not 0 <= self.canary_percentage <= 100:
            raise ValueError(
                "Canary traffic percentage must be between "
                "0 and 100."
            )

        if (
            self.stable_percentage
            + self.canary_percentage
            != 100
        ):
            raise ValueError(
                "Stable and canary traffic percentages "
                "must total 100."
            )

        if self.canary_percentage == 0:
            raise ValueError(
                "Canary traffic percentage must be greater than 0."
            )

        if self.canary_percentage == 100:
            raise ValueError(
                "Canary traffic percentage must be less than 100."
            )
