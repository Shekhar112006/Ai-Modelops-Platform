import pytest

from backend.app.services.deployment_recovery_policy import (
    DeploymentRecoveryPolicy,
    RecoveryAction,
)


@pytest.fixture
def policy() -> DeploymentRecoveryPolicy:
    return DeploymentRecoveryPolicy()


def evaluate(policy, **overrides):
    parameters = {
        "is_healthy": False,
        "deployment_status": "production",
        "consecutive_failures": 3,
        "previous_consecutive_failures": 2,
        "failure_threshold": 3,
    }
    parameters.update(overrides)
    return policy.evaluate(**parameters)


def test_threshold_crossing_approves_production_rollback(policy):
    decision = evaluate(policy)

    assert decision.action == RecoveryAction.ROLLBACK
    assert decision.eligible is True
    assert decision.reason == "failure_threshold_reached"


def test_threshold_crossing_approves_canary_rollback(policy):
    decision = evaluate(policy, deployment_status="canary")

    assert decision.action == RecoveryAction.ROLLBACK


def test_below_threshold_does_not_approve_rollback(policy):
    decision = evaluate(
        policy,
        consecutive_failures=2,
        previous_consecutive_failures=1,
    )

    assert decision.action == RecoveryAction.NONE
    assert decision.reason == "failure_threshold_not_reached"


def test_healthy_deployment_does_not_require_rollback(policy):
    decision = evaluate(
        policy,
        is_healthy=True,
        consecutive_failures=0,
        previous_consecutive_failures=3,
    )

    assert decision.action == RecoveryAction.NONE
    assert decision.reason == "deployment_healthy"


def test_staging_deployment_is_not_automatically_rolled_back(policy):
    decision = evaluate(policy, deployment_status="staging")

    assert decision.action == RecoveryAction.NONE
    assert decision.reason == "deployment_status_not_recoverable"


def test_already_processed_threshold_does_not_repeat_recovery(policy):
    decision = evaluate(
        policy,
        consecutive_failures=4,
        previous_consecutive_failures=3,
    )

    assert decision.action == RecoveryAction.NONE
    assert decision.reason == "threshold_already_processed"


def test_invalid_failure_threshold_is_rejected(policy):
    with pytest.raises(
        ValueError,
        match="failure_threshold must be at least 1",
    ):
        evaluate(policy, failure_threshold=0)
