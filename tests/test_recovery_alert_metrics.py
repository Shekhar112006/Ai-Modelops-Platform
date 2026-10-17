from __future__ import annotations

import pytest

from worker.task_metrics import (
    RECOVERY_ALERTS,
    record_recovery_alert,
)


@pytest.mark.parametrize(
    "event_type",
    [
        "failure_threshold_reached",
        "stale_recovery_claim_detected",
        "rollback_failed",
        "restoration_verification_failed",
    ],
)
def test_supported_recovery_alert_increments_counter(
    event_type: str,
) -> None:
    """Each supported recovery alert increments its own series."""

    counter = RECOVERY_ALERTS.labels(
        event_type=event_type,
        severity="error",
    )
    before = counter._value.get()

    record_recovery_alert(event_type)

    assert counter._value.get() == before + 1


def test_recovery_alert_supports_warning_severity() -> None:
    """Warning alerts use a separate severity series."""

    counter = RECOVERY_ALERTS.labels(
        event_type="failure_threshold_reached",
        severity="warning",
    )
    before = counter._value.get()

    record_recovery_alert(
        "failure_threshold_reached",
        severity="warning",
    )

    assert counter._value.get() == before + 1


def test_unknown_recovery_event_type_is_rejected() -> None:
    """Arbitrary event types must not create uncontrolled metric labels."""

    with pytest.raises(
        ValueError,
        match="Unsupported recovery alert event type",
    ):
        record_recovery_alert("deployment-123-specific-error")


def test_unknown_recovery_severity_is_rejected() -> None:
    """Only supported severities are accepted."""

    with pytest.raises(
        ValueError,
        match="Unsupported recovery alert severity",
    ):
        record_recovery_alert(
            "rollback_failed",
            severity="critical",
        )
