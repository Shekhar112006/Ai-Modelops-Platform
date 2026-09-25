import pytest

from backend.app.domain.deployment import (
    DeploymentStatus,
    InvalidDeploymentTransition,
    validate_deployment_transition,
)


def test_valid_deployment_transition() -> None:
    """A valid deployment transition should be accepted."""

    validate_deployment_transition(
        DeploymentStatus.CREATED,
        DeploymentStatus.VALIDATING,
    )


def test_invalid_deployment_transition() -> None:
    """An invalid deployment transition should be rejected."""

    with pytest.raises(InvalidDeploymentTransition):
        validate_deployment_transition(
            DeploymentStatus.CREATED,
            DeploymentStatus.PRODUCTION,
        )


def test_complete_happy_path_transitions() -> None:
    """The normal deployment lifecycle should be valid."""

    transitions = [
        (
            DeploymentStatus.CREATED,
            DeploymentStatus.VALIDATING,
        ),
        (
            DeploymentStatus.VALIDATING,
            DeploymentStatus.APPROVED,
        ),
        (
            DeploymentStatus.APPROVED,
            DeploymentStatus.STAGING,
        ),
        (
            DeploymentStatus.STAGING,
            DeploymentStatus.CANARY,
        ),
        (
            DeploymentStatus.CANARY,
            DeploymentStatus.PROMOTING,
        ),
        (
            DeploymentStatus.PROMOTING,
            DeploymentStatus.PRODUCTION,
        ),
    ]

    for current, target in transitions:
        validate_deployment_transition(current, target)


def test_rollback_path() -> None:
    """A production deployment should be able to enter rollback."""

    validate_deployment_transition(
        DeploymentStatus.PRODUCTION,
        DeploymentStatus.ROLLBACK,
    )

    validate_deployment_transition(
        DeploymentStatus.ROLLBACK,
        DeploymentStatus.ROLLED_BACK,
    )


def test_rolled_back_cannot_transition() -> None:
    """A rolled-back deployment is a terminal state."""

    with pytest.raises(InvalidDeploymentTransition):
        validate_deployment_transition(
            DeploymentStatus.ROLLED_BACK,
            DeploymentStatus.PRODUCTION,
        )
