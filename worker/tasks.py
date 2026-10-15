from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from worker.celery_app import celery_app

from backend.app.db.sync_session import get_session
from backend.app.models.training_job import TrainingJob
from ml.pipeline import run_model_selection_pipeline


@celery_app.task(
    bind=True,
    name="modelops.run_training_job",
)
def run_training_job(
    self,
    job_id: str,
) -> dict[str, object]:
    """Execute a ModelOps training job asynchronously."""

    session = get_session()

    try:
        job = session.get(
            TrainingJob,
            UUID(job_id),
        )

        if job is None:
            raise ValueError(
                f"Training job '{job_id}' was not found."
            )

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()

        result = run_model_selection_pipeline()

        job.status = "succeeded"
        job.selected_model_name = str(
            result["model_name"]
        )
        job.selected_model_version = str(
            result["model_version"]
        )
        job.completed_at = datetime.now(timezone.utc)

        session.commit()

        return result

    except Exception as exc:
        session.rollback()

        job = session.get(
            TrainingJob,
            UUID(job_id),
        )

        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)[
                :4000
            ]
            job.completed_at = datetime.now(
                timezone.utc
            )

            session.commit()

        raise

    finally:
        session.close()

@celery_app.task(
    name="modelops.check_deployment_health",
)
def check_deployment_health() -> dict[str, object]:
    """Check active deployment endpoints and persist the results."""

    from time import perf_counter

    import httpx

    from backend.app.core.config import settings
    from backend.app.repositories.deployment_health_check_repository import (
        DeploymentHealthCheckRepository,
    )

    session = get_session()
    repository = DeploymentHealthCheckRepository()

    checked = 0
    healthy_count = 0
    unhealthy_count = 0
    recovery_candidate_count = 0
    results: list[dict[str, object]] = []

    try:
        deployments = repository.list_monitorable_deployments(session)

        with httpx.Client(
            timeout=settings.health_check_timeout_seconds,
        ) as client:
            for deployment in deployments:
                endpoint = (
                    f"{deployment.model_endpoint.rstrip('/')}/health"
                )

                started = perf_counter()
                status_code: int | None = None
                error_message: str | None = None

                try:
                    response = client.get(endpoint)
                    status_code = response.status_code
                    response.raise_for_status()
                    is_healthy = 200 <= response.status_code < 300

                    if not is_healthy:
                        error_message = (
                            f"Unexpected health status: {status_code}"
                        )

                except Exception as exc:
                    is_healthy = False

                    if isinstance(exc, httpx.HTTPStatusError):
                        status_code = exc.response.status_code

                    error_message = (
                        f"{type(exc).__name__}: {exc}"
                    )[:1000]

                response_time_ms = max(
                    0,
                    round((perf_counter() - started) * 1000),
                )

                previous = repository.get_latest_for_deployment(
                    session,
                    deployment.id,
                )

                consecutive_failures = (
                    0
                    if is_healthy
                    else (
                        previous.consecutive_failures + 1
                        if previous is not None
                        else 1
                    )
                )

                recovery_eligible = (
                    not is_healthy
                    and consecutive_failures >= settings.health_check_failure_threshold
                    and deployment.status in {'canary', 'production'}
                )

                repository.create(
                    session,
                    deployment_id=deployment.id,
                    is_healthy=is_healthy,
                    response_time_ms=response_time_ms,
                    status_code=status_code,
                    consecutive_failures=consecutive_failures,
                    error_message=error_message,
                )

                # Persist each result so an issue with a later endpoint
                # does not discard earlier health-check records.
                session.commit()

                checked += 1

                if is_healthy:
                    healthy_count += 1
                else:
                    unhealthy_count += 1

                if recovery_eligible:
                    recovery_candidate_count += 1

                results.append(
                    {
                        "deployment_id": str(deployment.id),
                        "model_name": deployment.model_name,
                        "model_version": deployment.model_version,
                        "environment": deployment.environment,
                        "status": deployment.status,
                        "is_healthy": is_healthy,
                        "recovery_eligible": recovery_eligible,
                        "status_code": status_code,
                        "response_time_ms": response_time_ms,
                        "consecutive_failures": consecutive_failures,
                        "error_message": error_message,
                    }
                )

        return {
            "checked": checked,
            "healthy": healthy_count,
            "unhealthy": unhealthy_count,
            "recovery_candidates": recovery_candidate_count,
            "results": results,
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()
