from __future__ import annotations

import worker.tasks as task_module
from tests.test_deployment_health_check_task import run_health_check


def capture_recovery_alerts(monkeypatch) -> list[tuple[str, str]]:
    """Capture alert requests without changing Prometheus global counters."""

    calls: list[tuple[str, str]] = []

    def capture(event_type: str, severity: str = "error") -> None:
        calls.append((event_type, severity))

    monkeypatch.setattr(
        task_module.task_metrics,
        "record_recovery_alert",
        capture,
    )
    return calls


def test_failure_threshold_records_alert(monkeypatch) -> None:
    alerts = capture_recovery_alerts(monkeypatch)

    result, _, _ = run_health_check(
        monkeypatch,
        status_code=503,
        previous_failures=2,
    )

    assert result["recovery_candidates"] == 1
    assert ("failure_threshold_reached", "error") in alerts


def test_stale_claim_records_alert(monkeypatch) -> None:
    alerts = capture_recovery_alerts(monkeypatch)

    result, _, _ = run_health_check(
        monkeypatch,
        status_code=200,
        stale_claim_result=True,
    )

    assert result["results"][0]["stale_recovery_claim_detected"] is True
    assert ("stale_recovery_claim_detected", "error") in alerts


def test_rollback_failure_records_alert(monkeypatch) -> None:
    alerts = capture_recovery_alerts(monkeypatch)

    result, _, _ = run_health_check(
        monkeypatch,
        status_code=503,
        previous_failures=2,
        rollback_error=RuntimeError("simulated rollback failure"),
    )

    assert result["recovery_candidates"] == 1
    assert ("rollback_failed", "error") in alerts


def test_restoration_verification_failure_records_alert(monkeypatch) -> None:
    alerts = capture_recovery_alerts(monkeypatch)

    result, _, _ = run_health_check(
        monkeypatch,
        status_code=503,
        previous_failures=2,
        restored_status_code=503,
    )

    assert result["recovery_candidates"] == 1
    assert (
        "restoration_verification_failed",
        "error",
    ) in alerts
