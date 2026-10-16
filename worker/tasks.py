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
    from backend.app.repositories.deployment_recovery_state_repository import (
        DeploymentRecoveryStateRepository,
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
    recovery_state_repository = DeploymentRecoveryStateRepository()
    policy = DeploymentRecoveryPolicy()

    checked = 0
    healthy_count = 0
    unhealthy_count = 0
    recovery_candidate_count = 0
    results: list[dict[str, object]] = []

    try:
        deployments = health_repository.list_monitorable_deployments(session)

        # Inspect recovery states independently of deployment monitoring
        # status so interrupted claims cannot escape detection.
        stale_claims_detected: set[UUID] = set()
        stale_candidate_ids = (
            recovery_state_repository.list_stale_candidate_ids(
                session,
                timeout_seconds=settings.recovery_claim_timeout_seconds,
            )
        )

        for stale_deployment_id in stale_candidate_ids:
            stale_marked = recovery_state_repository.mark_stale_failed(
                session,
                deployment_id=stale_deployment_id,
                timeout_seconds=settings.recovery_claim_timeout_seconds,
            )

            # Only the task that performs the conditional transition records
            # the event; concurrent tasks cannot duplicate this event.
            if not stale_marked:
                continue

            recovery_repository.create(
                session,
                deployment_id=stale_deployment_id,
                event_type="stale_recovery_claim_detected",
                severity="error",
                message=(
                    f"Recovery claim for deployment {stale_deployment_id} "
                    "exceeded the configured timeout. Automatic retry was "
                    "suppressed pending reconciliation."
                ),
                consecutive_failures=0,
                details={
                    "claim_timeout_seconds": (
                        settings.recovery_claim_timeout_seconds
                    ),
                    "requires_reconciliation": True,
                },
            )
            stale_claims_detected.add(stale_deployment_id)

        # Make stale-state transitions durable before health checks or
        # rollback only when this task actually marked a claim stale.
        if stale_claims_detected:
            session.commit()

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
                recovery_claimed = False
                if is_healthy:
                    recovery_state_repository.reset_after_healthy(
                        session,
                        deployment_id=deployment_id,
                    )
                elif recovery_eligible:
                    recovery_claimed = recovery_state_repository.claim(
                        session,
                        deployment_id=deployment_id,
                        consecutive_failures=consecutive_failures,
                    )

                event_details: dict[str, object] = {
                    "model_name": model_name,
                    "model_version": model_version,
                    "environment": environment,
                    "deployment_status": deployment_status,
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                    "previous_consecutive_failures": previous_failure_count,
                    "recovery_claimed": recovery_claimed,
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

                # Report whether the global stale-claim scan marked
                # this deployment during the current task execution.
                stale_claim_marked = deployment_id in stale_claims_detected

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

                if threshold_crossed and (not recovery_eligible or recovery_claimed):
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

                recovery_outcome: dict[str, object]
                if recovery_eligible and not recovery_claimed:
                    recovery_outcome = {
                        "attempted": False,
                        "status": "suppressed",
                        "reason": "recovery_state_not_idle",
                    }
                else:
                    recovery_outcome = {
                        "attempted": False,
                        "status": "not_required",
                        "reason": decision.reason,
                    }

                # Persist the health result and the rollback intent before
                # invoking the separate asynchronous deployment transaction.
                if recovery_claimed:
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

                if recovery_claimed:
                    recovery_candidate_count += 1

                    try:
                        rollback_result = execute_automated_rollback(
                            deployment_id
                        )
                    except Exception as exc:
                        rollback_error = (
                            f"{type(exc).__name__}: {exc}"
                        )[:1000]

                        # The recovery claim has already been committed.
                        session.rollback()

                        recovery_state_repository.mark_failed(
                            session,
                            deployment_id=deployment_id,
                            error=rollback_error,
                        )

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

                        restored_deployment_id = rollback_result.get(
                            "restored_deployment_id"
                        )
                        restored_endpoint = rollback_result.get(
                            "restored_model_endpoint"
                        )
                        restored_status = rollback_result.get(
                            "restored_status"
                        )
                        restored_traffic = str(
                            rollback_result.get(
                                "restored_traffic_percentage",
                                "",
                            )
                        )

                        restoration_verified = False
                        verification_status_code: int | None = None
                        verification_error: str | None = None

                        try:
                            if not restored_deployment_id:
                                raise ValueError(
                                    "Rollback did not identify the restored deployment."
                                )

                            if not restored_endpoint:
                                raise ValueError(
                                    "Restored deployment has no health endpoint."
                                )

                            if restored_status not in {"staging", "production"}:
                                raise ValueError(
                                    "Restored deployment is not in a stable state: "
                                    f"{restored_status!r}."
                                )

                            if restored_traffic != "100":
                                raise ValueError(
                                    "Restored deployment does not have 100% traffic: "
                                    f"{restored_traffic!r}."
                                )

                            verification_response = client.get(
                                f"{restored_endpoint.rstrip('/')}/health"
                            )
                            verification_status_code = (
                                verification_response.status_code
                            )
                            verification_response.raise_for_status()

                            if not (
                                200
                                <= verification_status_code
                                < 300
                            ):
                                raise ValueError(
                                    "Restored deployment returned an unexpected "
                                    f"health status: {verification_status_code}."
                                )

                            restoration_verified = True

                        except Exception as verification_exc:
                            if isinstance(
                                verification_exc,
                                httpx.HTTPStatusError,
                            ):
                                verification_status_code = (
                                    verification_exc.response.status_code
                                )

                            verification_error = (
                                f"{type(verification_exc).__name__}: "
                                f"{verification_exc}"
                            )[:1000]

                        verification_details: dict[str, object] = {
                            **event_details,
                            "rollback_result": rollback_result,
                            "restored_deployment_id": restored_deployment_id,
                            "restored_health_status_code": (
                                verification_status_code
                            ),
                            "restoration_verified": restoration_verified,
                        }

                        if verification_error is not None:
                            verification_details["verification_error"] = (
                                verification_error
                            )

                        if restoration_verified:
                            recovery_repository.create(
                                session,
                                deployment_id=deployment_id,
                                event_type="restoration_verification_succeeded",
                                severity="info",
                                message=(
                                    f"Restored deployment {restored_deployment_id} "
                                    "passed its health check after rollback."
                                ),
                                consecutive_failures=0,
                                details=verification_details,
                            )

                            recovery_outcome = {
                                "attempted": True,
                                "status": "succeeded",
                                "reason": "restoration_verified",
                                "deployment_id": rollback_result["deployment_id"],
                                "deployment_status": rollback_result["status"],
                                "restored_deployment_id": restored_deployment_id,
                                "restored_status": restored_status,
                                "restored_health_status_code": (
                                    verification_status_code
                                ),
                            }

                        else:
                            recovery_repository.create(
                                session,
                                deployment_id=deployment_id,
                                event_type="restoration_verification_failed",
                                severity="error",
                                message=(
                                    f"Rollback completed, but restored deployment "
                                    f"{restored_deployment_id} failed verification."
                                ),
                                consecutive_failures=0,
                                details=verification_details,
                            )

                            recovery_outcome = {
                                "attempted": True,
                                "status": "verification_failed",
                                "reason": "restoration_verification_failed",
                                "deployment_id": rollback_result["deployment_id"],
                                "deployment_status": rollback_result["status"],
                                "restored_deployment_id": restored_deployment_id,
                                "restored_health_status_code": (
                                    verification_status_code
                                ),
                                "error": verification_error,
                            }

                        if restoration_verified:
                            recovery_state_repository.mark_completed(
                                session,
                                deployment_id=deployment_id,
                            )
                        else:
                            recovery_state_repository.mark_failed(
                                session,
                                deployment_id=deployment_id,
                                error=(
                                    verification_error
                                    or "Restoration verification failed."
                                ),
                            )

                        session.commit()

                results.append(
                    {
                        "deployment_id": str(deployment_id),
                        "model_name": model_name,
                        "model_version": model_version,
                        "environment": environment,
                        "status": deployment_status,
                        "is_healthy": is_healthy,
                        "recovery_eligible": recovery_eligible,
                        "recovery_claimed": recovery_claimed,
                        "stale_recovery_claim_detected": stale_claim_marked,
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
