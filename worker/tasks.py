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
    """Check deployment health, record events, and recover when eligible."""

    from time import perf_counter

    import httpx

    from backend.app.core.config import settings
    from backend.app.repositories.deployment_health_check_repository import (
        DeploymentHealthCheckRepository,
    )
    from backend.app.repositories.deployment_recovery_event_repository import (
        DeploymentRecoveryEventRepository,
    )
    from backend.app.services.deployment_recovery_policy import (
        DeploymentRecoveryPolicy,
    )
    from backend.app.services.deployment_recovery_executor import (
        execute_automated_rollback,
    )

    session = get_session()
    health_repository = DeploymentHealthCheckRepository()
    recovery_repository = DeploymentRecoveryEventRepository()
    policy = DeploymentRecoveryPolicy()

    checked = 0
    healthy_count = 0
    unhealthy_count = 0
    recovery_candidate_count = 0
    results: list[dict[str, object]] = []

    try:
        deployments = health_repository.list_monitorable_deployments(session)

        with httpx.Client(
            timeout=settings.health_check_timeout_seconds,
        ) as client:
            for deployment in deployments:
                deployment_id = deployment.id
                model_name = deployment.model_name
                model_version = deployment.model_version
                environment = deployment.environment
                deployment_status = deployment.status

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

                previous = health_repository.get_latest_for_deployment(
                    session,
                    deployment_id,
                )

                previous_failure_count = (
                    previous.consecutive_failures
                    if previous is not None
                    else 0
                )

                consecutive_failures = (
                    0
                    if is_healthy
                    else previous_failure_count + 1
                )

                decision = policy.evaluate(
                    is_healthy=is_healthy,
                    deployment_status=deployment_status,
                    consecutive_failures=consecutive_failures,
                    previous_consecutive_failures=previous_failure_count,
                    failure_threshold=settings.health_check_failure_threshold,
                )

                recovery_eligible = decision.eligible

                event_details: dict[str, object] = {
                    "model_name": model_name,
                    "model_version": model_version,
                    "environment": environment,
                    "deployment_status": deployment_status,
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                    "previous_consecutive_failures": previous_failure_count,
                }

                if error_message is not None:
                    event_details["error_message"] = error_message

                health_repository.create(
                    session,
                    deployment_id=deployment_id,
                    is_healthy=is_healthy,
                    response_time_ms=response_time_ms,
                    status_code=status_code,
                    consecutive_failures=consecutive_failures,
                    error_message=error_message,
                )

                # Record the start of a new consecutive failure streak.
                if (
                    not is_healthy
                    and previous_failure_count == 0
                ):
                    recovery_repository.create(
                        session,
                        deployment_id=deployment_id,
                        event_type="health_check_failed",
                        severity="warning",
                        message=(
                            f"Health check failed for {model_name} "
                            f"version {model_version}."
                        ),
                        consecutive_failures=consecutive_failures,
                        details=event_details,
                    )

                # Record threshold crossing without repeating it on later checks.
                threshold_crossed = (
                    not is_healthy
                    and previous_failure_count
                    < settings.health_check_failure_threshold
                    and consecutive_failures
                    >= settings.health_check_failure_threshold
                )

                if threshold_crossed:
                    recovery_repository.create(
                        session,
                        deployment_id=deployment_id,
                        event_type="failure_threshold_reached",
                        severity="error",
                        message=(
                            f"Deployment {model_name} version "
                            f"{model_version} reached the configured "
                            "health-check failure threshold."
                        ),
                        consecutive_failures=consecutive_failures,
                        details={
                            **event_details,
                            "failure_threshold": (
                                settings.health_check_failure_threshold
                            ),
                            "recovery_eligible": recovery_eligible,
                            "recovery_reason": decision.reason,
                        },
                    )

                # Record recovery even when no rollback is necessary.
                if (
                    is_healthy
                    and previous_failure_count > 0
                ):
                    recovery_repository.create(
                        session,
                        deployment_id=deployment_id,
                        event_type="deployment_health_recovered",
                        severity="info",
                        message=(
                            f"Deployment {model_name} version "
                            f"{model_version} recovered its health."
                        ),
                        consecutive_failures=0,
                        details=event_details,
                    )

                recovery_outcome: dict[str, object] = {
                    "attempted": False,
                    "status": "not_required",
                    "reason": decision.reason,
                }

                # Persist the health result and the rollback intent before
                # invoking the separate asynchronous deployment transaction.
                if recovery_eligible:
                    recovery_repository.create(
                        session,
                        deployment_id=deployment_id,
                        event_type="rollback_started",
                        severity="warning",
                        message=(
                            f"Automatic rollback started for {model_name} "
                            f"version {model_version}."
                        ),
                        consecutive_failures=consecutive_failures,
                        details=event_details,
                    )

                session.commit()

                checked += 1

                if is_healthy:
                    healthy_count += 1
                else:
                    unhealthy_count += 1

                if recovery_eligible:
                    recovery_candidate_count += 1

                    try:
                        rollback_result = execute_automated_rollback(
                            deployment_id
                        )
                    except Exception as exc:
                        rollback_error = (
                            f"{type(exc).__name__}: {exc}"
                        )[:1000]

                        # The preceding health-check commit is already durable.
                        session.rollback()

                        recovery_repository.create(
                            session,
                            deployment_id=deployment_id,
                            event_type="rollback_failed",
                            severity="error",
                            message=(
                                f"Automatic rollback failed for {model_name} "
                                f"version {model_version}."
                            ),
                            consecutive_failures=consecutive_failures,
                            details={
                                **event_details,
                                "error": rollback_error,
                            },
                        )
                        session.commit()

                        recovery_outcome = {
                            "attempted": True,
                            "status": "failed",
                            "reason": "rollback_execution_failed",
                            "error": rollback_error,
                        }
                    else:
                        recovery_repository.create(
                            session,
                            deployment_id=deployment_id,
                            event_type="rollback_succeeded",
                            severity="info",
                            message=(
                                f"Automatic rollback completed for "
                                f"{model_name} version {model_version}."
                            ),
                            consecutive_failures=consecutive_failures,
                            details={
                                **event_details,
                                "rollback_result": rollback_result,
                            },
                        )
                        session.commit()

                        recovery_outcome = {
                            "attempted": True,
                            "status": "succeeded",
                            "reason": "rollback_completed",
                            "deployment_id": rollback_result["deployment_id"],
                            "deployment_status": rollback_result["status"],
                        }

                results.append(
                    {
                        "deployment_id": str(deployment_id),
                        "model_name": model_name,
                        "model_version": model_version,
                        "environment": environment,
                        "status": deployment_status,
                        "is_healthy": is_healthy,
                        "recovery_eligible": recovery_eligible,
                        "status_code": status_code,
                        "response_time_ms": response_time_ms,
                        "consecutive_failures": consecutive_failures,
                        "error_message": error_message,
                        "recovery": recovery_outcome,
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
