"""Opt-in integration tests for recovery claims against real PostgreSQL."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.engine import make_url

from backend.app.core.config import settings
from backend.app.db.sync_session import SessionFactory
from backend.app.models.deployment import Deployment
from backend.app.models.deployment_recovery_state import (
    DeploymentRecoveryState,
)
from backend.app.models.project import Project
from backend.app.repositories.deployment_recovery_state_repository import (
    DeploymentRecoveryStateRepository,
)


def require_postgres_integration() -> None:
    """Require explicit opt-in and restrict the target database."""
    if os.getenv("RUN_POSTGRES_INTEGRATION") != "1":
        pytest.skip(
            "Set RUN_POSTGRES_INTEGRATION=1 to run real PostgreSQL tests."
        )

    url = make_url(settings.database_url)

    if url.drivername != "postgresql+psycopg":
        pytest.fail(
            "Integration test requires the postgresql+psycopg driver."
        )

    if url.database not in {"modelops", "modelops_test"}:
        pytest.fail(
            "Database safety check failed. Expected modelops or modelops_test."
        )


def create_test_deployment() -> tuple[UUID, UUID]:
    """Create an isolated project and deployment for this test."""
    project_id: UUID
    deployment_id: UUID

    with SessionFactory() as session:
        project = Project(
            name=f"pytest-recovery-{uuid4().hex}",
            description="Temporary recovery-state integration test.",
        )
        session.add(project)
        session.flush()

        deployment = Deployment(
            project_id=project.id,
            model_name="pytest-recovery-model",
            model_version="integration-test",
            environment="staging",
            status="production",
            traffic_percentage=100,
            model_endpoint="http://127.0.0.1:1",
        )
        session.add(deployment)
        session.commit()

        project_id = project.id
        deployment_id = deployment.id

    return project_id, deployment_id


def cleanup_test_deployment(
    project_id: UUID | None,
    deployment_id: UUID | None,
) -> None:
    """Delete only records created for this test."""
    with SessionFactory() as session:
        if deployment_id is not None:
            session.execute(
                delete(DeploymentRecoveryState).where(
                    DeploymentRecoveryState.deployment_id == deployment_id
                )
            )
            session.execute(
                delete(Deployment).where(Deployment.id == deployment_id)
            )

        if project_id is not None:
            session.execute(
                delete(Project).where(Project.id == project_id)
            )

        session.commit()


def test_postgres_concurrent_claim_and_recovery_state_transitions() -> None:
    """Only one concurrent claimant succeeds; state changes are persisted."""
    require_postgres_integration()

    project_id: UUID | None = None
    deployment_id: UUID | None = None

    try:
        project_id, deployment_id = create_test_deployment()
        repository = DeploymentRecoveryStateRepository()
        barrier = Barrier(2)

        def attempt_claim() -> bool:
            """Compete for a claim using a separate PostgreSQL session."""
            with SessionFactory() as session:
                barrier.wait(timeout=15)

                claimed = repository.claim(
                    session,
                    deployment_id=deployment_id,
                    consecutive_failures=3,
                )
                session.commit()
                return claimed

        # Two independent sessions attempt the same initially absent state.
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt_claim),
                executor.submit(attempt_claim),
            ]
            results = [future.result(timeout=30) for future in futures]

        assert sorted(results) == [False, True], (
            f"Expected exactly one successful claimant; got {results!r}"
        )

        # Verify that the winning claim was persisted in PostgreSQL.
        with SessionFactory() as session:
            state = session.scalars(
                select(DeploymentRecoveryState).where(
                    DeploymentRecoveryState.deployment_id == deployment_id
                )
            ).one()

            assert state.status == "in_progress"
            assert state.consecutive_failures == 3

            # An in-progress state blocks another claim.
            assert repository.claim(
                session,
                deployment_id=deployment_id,
                consecutive_failures=4,
            ) is False
            session.commit()

            # Successful recovery transitions to completed.
            assert repository.mark_completed(
                session,
                deployment_id=deployment_id,
            ) is True
            session.commit()

            assert repository.claim(
                session,
                deployment_id=deployment_id,
                consecutive_failures=5,
            ) is False
            session.commit()

            # A healthy observation resets the completed state.
            assert repository.reset_after_healthy(
                session,
                deployment_id=deployment_id,
            ) is True
            session.commit()

            # A new failure episode may now claim recovery.
            assert repository.claim(
                session,
                deployment_id=deployment_id,
                consecutive_failures=3,
            ) is True
            session.commit()

            # Failed recovery also blocks claims until the next healthy reset.
            assert repository.mark_failed(
                session,
                deployment_id=deployment_id,
                error="Integration test failure.",
            ) is True
            session.commit()

            # Verify persisted state through a fresh session. The claim's
            # PostgreSQL upsert may leave an existing ORM instance stale.
            with SessionFactory() as verification_session:
                failed_state = verification_session.scalars(
                    select(DeploymentRecoveryState).where(
                        DeploymentRecoveryState.deployment_id == deployment_id
                    )
                ).one()

                assert failed_state.status == "failed"
                assert failed_state.last_error == "Integration test failure."

                # A failed recovery must block another claim.
                assert repository.claim(
                    verification_session,
                    deployment_id=deployment_id,
                    consecutive_failures=3,
                ) is False
                verification_session.commit()

            assert repository.reset_after_healthy(
                session,
                deployment_id=deployment_id,
            ) is True
            session.commit()

            # Confirm another recovery claim succeeds after the reset.
            assert repository.claim(
                session,
                deployment_id=deployment_id,
                consecutive_failures=3,
            ) is True
            session.commit()

        # Simulate a claim that has exceeded its recovery timeout.
        with SessionFactory() as session:
            session.execute(
                update(DeploymentRecoveryState)
                .where(
                    DeploymentRecoveryState.deployment_id == deployment_id
                )
                .values(
                    claimed_at=(
                        datetime.now(timezone.utc)
                        - timedelta(seconds=600)
                    )
                )
            )
            # Simulate a rollback changing the deployment out of a
            # normally monitored state before the worker crashes.
            session.execute(
                update(Deployment)
                .where(Deployment.id == deployment_id)
                .values(status="rolled_back", traffic_percentage=0)
            )
            session.commit()

        # Stale recovery discovery must not depend on deployment status.
        with SessionFactory() as session:
            assert repository.list_stale_candidate_ids(
                session,
                timeout_seconds=300.0,
            ) == [deployment_id]

        # Expired claims become failed, but are not released for retry.
        with SessionFactory() as session:
            assert repository.mark_stale_failed(
                session,
                deployment_id=deployment_id,
                timeout_seconds=300.0,
            ) is True
            session.commit()

        with SessionFactory() as session:
            stale_state = session.scalars(
                select(DeploymentRecoveryState).where(
                    DeploymentRecoveryState.deployment_id == deployment_id
                )
            ).one()

            assert stale_state.status == "failed"
            assert stale_state.last_error.startswith(
                "Stale recovery claim detected:"
            )

            assert repository.claim(
                session,
                deployment_id=deployment_id,
                consecutive_failures=4,
            ) is False

            assert repository.reset_after_healthy(
                session,
                deployment_id=deployment_id,
            ) is False
            session.commit()

        # Simulate the original worker completing after stale detection.
        with SessionFactory() as session:
            assert repository.mark_completed(
                session,
                deployment_id=deployment_id,
            ) is True
            session.commit()

        with SessionFactory() as session:
            completed_state = session.scalars(
                select(DeploymentRecoveryState).where(
                    DeploymentRecoveryState.deployment_id == deployment_id
                )
            ).one()

            assert completed_state.status == "completed"

            assert repository.reset_after_healthy(
                session,
                deployment_id=deployment_id,
            ) is True
            session.commit()

            assert repository.claim(
                session,
                deployment_id=deployment_id,
                consecutive_failures=3,
            ) is True
            session.commit()

    finally:
        cleanup_test_deployment(project_id, deployment_id)
