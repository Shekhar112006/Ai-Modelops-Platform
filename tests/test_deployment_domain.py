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


def test_valid_canary_traffic() -> None:
    """Canary traffic must be between 1% and 99%."""

    from backend.app.domain.deployment import (
        validate_canary_traffic,
    )

    validate_canary_traffic(1)
    validate_canary_traffic(5)
    validate_canary_traffic(50)
    validate_canary_traffic(99)


def test_zero_canary_traffic_is_invalid() -> None:
    """Zero percent is not a valid canary allocation."""

    from backend.app.domain.deployment import (
        validate_canary_traffic,
    )

    with pytest.raises(ValueError):
        validate_canary_traffic(0)


def test_full_canary_traffic_is_invalid() -> None:
    """One hundred percent represents full traffic, not a canary."""

    from backend.app.domain.deployment import (
        validate_canary_traffic,
    )

    with pytest.raises(ValueError):
        validate_canary_traffic(100)


def test_negative_canary_traffic_is_invalid() -> None:
    """Negative traffic percentages are invalid."""

    from backend.app.domain.deployment import (
        validate_canary_traffic,
    )

    with pytest.raises(ValueError):
        validate_canary_traffic(-1)


def test_valid_traffic_allocation() -> None:
    """Stable and canary traffic should total 100%."""

    from backend.app.domain.deployment import (
        TrafficAllocation,
    )

    allocation = TrafficAllocation(
        stable_percentage=95,
        canary_percentage=5,
    )

    assert allocation.stable_percentage == 95
    assert allocation.canary_percentage == 5


def test_traffic_allocation_must_total_100() -> None:
    """Traffic percentages that do not total 100% are invalid."""

    from backend.app.domain.deployment import (
        TrafficAllocation,
    )

    with pytest.raises(ValueError):
        TrafficAllocation(
            stable_percentage=80,
            canary_percentage=30,
        )


def test_zero_canary_allocation_is_invalid() -> None:
    """A zero-percent canary is not a canary deployment."""

    from backend.app.domain.deployment import (
        TrafficAllocation,
    )

    with pytest.raises(ValueError):
        TrafficAllocation(
            stable_percentage=100,
            canary_percentage=0,
        )


def test_full_canary_allocation_is_invalid() -> None:
    """A 100-percent canary is no longer a canary release."""

    from backend.app.domain.deployment import (
        TrafficAllocation,
    )

    with pytest.raises(ValueError):
        TrafficAllocation(
            stable_percentage=0,
            canary_percentage=100,
        )
