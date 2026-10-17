"""Prometheus metrics for Celery task execution."""

from __future__ import annotations

from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram, multiprocess


TASK_EXECUTIONS = Counter(
    "modelops_celery_task_executions",
    "Completed Celery task executions by outcome.",
    ["task_name", "outcome"],
)

TASK_FAILURES = Counter(
    "modelops_celery_task_failures",
    "Failed Celery task executions.",
    ["task_name", "exception_type"],
)

TASK_DURATION = Histogram(
    "modelops_celery_task_duration_seconds",
    "Celery task execution duration in seconds.",
    ["task_name"],
    buckets=(
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        30.0,
        60.0,
        300.0,
    ),
)

TASKS_IN_PROGRESS = Gauge(
    "modelops_celery_tasks_in_progress",
    "Number of Celery tasks currently executing.",
    ["task_name"],
    multiprocess_mode="livesum",
)


_task_start_times: dict[str, tuple[str, float]] = {}


def _resolve_task_name(sender=None, task=None) -> str:
    """Resolve a stable task name from a Celery signal."""

    for candidate in (sender, task):
        name = getattr(candidate, "name", None)
        if name:
            return str(name)

    return "unknown"


def record_task_prerun(
    sender=None,
    task_id=None,
    task=None,
    **kwargs,
) -> None:
    """Track the start time and active count of a task."""

    task_name = _resolve_task_name(sender, task)

    if task_id is not None:
        _task_start_times[str(task_id)] = (
            task_name,
            perf_counter(),
        )

    TASKS_IN_PROGRESS.labels(task_name=task_name).inc()


def record_task_postrun(
    sender=None,
    task_id=None,
    task=None,
    state=None,
    **kwargs,
) -> None:
    """Record task outcome and duration after execution."""

    task_name = _resolve_task_name(sender, task)
    started = (
        _task_start_times.pop(str(task_id), None)
        if task_id is not None
        else None
    )

    if started is not None:
        task_name, started_at = started

        TASK_DURATION.labels(
            task_name=task_name,
        ).observe(perf_counter() - started_at)

        TASKS_IN_PROGRESS.labels(
            task_name=task_name,
        ).dec()

    normalized_state = str(state or "unknown").lower()

    if normalized_state == "success":
        outcome = "success"
    elif normalized_state == "failure":
        outcome = "failure"
    else:
        outcome = "other"

    TASK_EXECUTIONS.labels(
        task_name=task_name,
        outcome=outcome,
    ).inc()


def record_task_failure(
    sender=None,
    exception=None,
    **kwargs,
) -> None:
    """Increment the failure counter for a failed task."""

    task_name = _resolve_task_name(sender)

    exception_type = (
        type(exception).__name__
        if exception is not None
        else "UnknownException"
    )

    TASK_FAILURES.labels(
        task_name=task_name,
        exception_type=exception_type,
    ).inc()


def mark_worker_process_dead(
    pid: int | None = None,
    **kwargs,
) -> None:
    """Clean up live multiprocess gauge files for an exited worker."""

    if pid is not None:
        multiprocess.mark_process_dead(int(pid))
