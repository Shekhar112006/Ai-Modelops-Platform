from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from worker import task_metrics


def test_successful_task_records_execution_and_duration() -> None:
    """Successful task execution increments metrics and clears its gauge."""

    task_name = f"modelops.test_task_{uuid4().hex}"
    task_id = uuid4().hex
    sender = SimpleNamespace(name=task_name)

    execution = task_metrics.TASK_EXECUTIONS.labels(
        task_name=task_name,
        outcome="success",
    )
    duration = task_metrics.TASK_DURATION.labels(
        task_name=task_name,
    )
    in_progress = task_metrics.TASKS_IN_PROGRESS.labels(
        task_name=task_name,
    )

    executions_before = execution._value.get()
    duration_count_before = duration._sum.get()
    in_progress_before = in_progress._value.get()

    task_metrics.record_task_prerun(
        sender=sender,
        task_id=task_id,
        task=sender,
    )

    assert in_progress._value.get() == in_progress_before + 1

    task_metrics.record_task_postrun(
        sender=sender,
        task_id=task_id,
        task=sender,
        state="SUCCESS",
    )

    assert execution._value.get() == executions_before + 1
    assert duration._sum.get() >= duration_count_before
    assert in_progress._value.get() == in_progress_before


def test_failed_task_records_execution_and_exception() -> None:
    """Failure signals increment both execution and failure counters."""

    task_name = f"modelops.test_failure_{uuid4().hex}"
    task_id = uuid4().hex
    sender = SimpleNamespace(name=task_name)

    execution = task_metrics.TASK_EXECUTIONS.labels(
        task_name=task_name,
        outcome="failure",
    )
    failure = task_metrics.TASK_FAILURES.labels(
        task_name=task_name,
        exception_type="ValueError",
    )

    executions_before = execution._value.get()
    failures_before = failure._value.get()

    task_metrics.record_task_prerun(
        sender=sender,
        task_id=task_id,
        task=sender,
    )

    task_metrics.record_task_failure(
        sender=sender,
        exception=ValueError("test failure"),
    )

    task_metrics.record_task_postrun(
        sender=sender,
        task_id=task_id,
        task=sender,
        state="FAILURE",
    )

    assert execution._value.get() == executions_before + 1
    assert failure._value.get() == failures_before + 1

    assert (
        task_metrics.TASKS_IN_PROGRESS.labels(
            task_name=task_name,
        )._value.get()
        == 0
    )


def test_unknown_task_state_uses_other_outcome() -> None:
    """Unrecognized task states are recorded without unbounded labels."""

    task_name = f"modelops.test_other_{uuid4().hex}"
    sender = SimpleNamespace(name=task_name)

    execution = task_metrics.TASK_EXECUTIONS.labels(
        task_name=task_name,
        outcome="other",
    )
    before = execution._value.get()

    task_metrics.record_task_postrun(
        sender=sender,
        task_id=None,
        task=sender,
        state="REVOKED",
    )

    assert execution._value.get() == before + 1
