from __future__ import annotations
import pytest

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.app.db.session import AsyncSessionFactory
from backend.app.db.sync_session import SessionFactory
from backend.app.domain.deployment import DeploymentEnvironment
from backend.app.main import app
from backend.app.models.deployment import Deployment
from backend.app.models.project import Project
from backend.app.repositories.deployment_repository import DeploymentRepository
from backend.app.repositories.project_repository import ProjectRepository
from backend.app.services.deployment_service import DeploymentService


client = TestClient(app)

MODEL_NAME = "demo-classifier"
STABLE_VERSION = "4"
CANARY_VERSION = "5"

STABLE_ENDPOINT = "http://stable-test:8000"
CANARY_ENDPOINT = "http://canary-test:8000"


def create_test_project() -> UUID:
    """Create a temporary project for canary integration tests."""

    response = client.post(
        "/api/v1/projects",
        json={
            "name": "canary-test-project",
            "description": "Temporary canary deployment test project",
        },
    )

    assert response.status_code == 201

    return UUID(response.json()["id"])


def cleanup_project(project_id: UUID) -> None:
    """Remove temporary canary deployment test data."""

    with SessionFactory() as session:
        session.execute(
            delete(Deployment).where(
                Deployment.project_id == project_id
            )
        )

        session.execute(
            delete(Project).where(
                Project.id == project_id
            )
        )

        session.commit()


async def create_stable_deployment(
    project_id: UUID,
) -> None:
    """Create and activate a temporary stable deployment."""

    service = DeploymentService(
        project_repository=ProjectRepository(),
        deployment_repository=DeploymentRepository(),
    )

    async with AsyncSessionFactory() as session:
        deployment = await service.create_deployment(
            session=session,
            project_id=project_id,
            model_name=MODEL_NAME,
            model_version=STABLE_VERSION,
            environment=DeploymentEnvironment.STAGING,
        )

        await service.activate_staging_deployment(
            session=session,
            deployment_id=deployment.id,
            endpoint=STABLE_ENDPOINT,
        )


def test_create_canary_deployment() -> None:
    """A 5% canary should reduce stable traffic to 95%."""

    import asyncio

    project_id = create_test_project()

    try:
        asyncio.run(
            create_stable_deployment(project_id)
        )

        async def run_canary_test() -> None:
            service = DeploymentService(
                project_repository=ProjectRepository(),
                deployment_repository=DeploymentRepository(),
            )

            async with AsyncSessionFactory() as session:
                canary = await service.create_canary_deployment(
                    session=session,
                    project_id=project_id,
                    model_name=MODEL_NAME,
                    model_version=CANARY_VERSION,
                    environment=DeploymentEnvironment.STAGING,
                    endpoint=CANARY_ENDPOINT,
                    canary_percentage=5,
                )

                assert canary.status == "canary"
                assert canary.traffic_percentage == 5
                assert canary.model_version == CANARY_VERSION

                deployments = (
                    await service.deployment_repository.list_by_project(
                        session,
                        project_id,
                    )
                )

                active = [
                    deployment
                    for deployment in deployments
                    if deployment.status in {
                        "staging",
                        "canary",
                        "promoting",
                        "production",
                    }
                ]

                assert len(active) == 2

                stable = next(
                    deployment
                    for deployment in active
                    if deployment.model_version == STABLE_VERSION
                )

                assert stable.traffic_percentage == 95
                assert canary.traffic_percentage == 5
                assert (
                    stable.traffic_percentage
                    + canary.traffic_percentage
                    == 100
                )

        asyncio.run(run_canary_test())

    finally:
        cleanup_project(project_id)


def test_canary_percentage_too_large() -> None:
    """A canary cannot consume the entire stable allocation."""

    import asyncio

    project_id = create_test_project()

    try:
        asyncio.run(
            create_stable_deployment(project_id)
        )

        async def run_test() -> None:
            service = DeploymentService(
                project_repository=ProjectRepository(),
                deployment_repository=DeploymentRepository(),
            )

            async with AsyncSessionFactory() as session:
                try:
                    await service.create_canary_deployment(
                        session=session,
                        project_id=project_id,
                        model_name=MODEL_NAME,
                        model_version=CANARY_VERSION,
                        environment=DeploymentEnvironment.STAGING,
                        endpoint=CANARY_ENDPOINT,
                        canary_percentage=100,
                    )
                except ValueError:
                    return

                raise AssertionError(
                    "100% canary traffic should be rejected."
                )

        asyncio.run(run_test())

    finally:
        cleanup_project(project_id)


def test_canary_requires_active_stable_deployment() -> None:
    """A canary cannot be created without an active stable deployment."""

    import asyncio

    project_id = create_test_project()

    try:
        async def run_test() -> None:
            service = DeploymentService(
                project_repository=ProjectRepository(),
                deployment_repository=DeploymentRepository(),
            )

            async with AsyncSessionFactory() as session:
                try:
                    await service.create_canary_deployment(
                        session=session,
                        project_id=project_id,
                        model_name=MODEL_NAME,
                        model_version=CANARY_VERSION,
                        environment=DeploymentEnvironment.STAGING,
                        endpoint=CANARY_ENDPOINT,
                        canary_percentage=5,
                    )
                except Exception as exc:
                    assert "No active deployment" in str(exc)
                    return

                raise AssertionError(
                    "Canary creation should require an active deployment."
                )

        asyncio.run(run_test())

    finally:
        cleanup_project(project_id)


def test_promote_canary_to_production() -> None:
    """A canary should become production with 100% traffic."""

    import asyncio

    project_id = create_test_project()

    try:
        asyncio.run(
            create_stable_deployment(project_id)
        )

        async def run_test() -> None:
            service = DeploymentService(
                project_repository=ProjectRepository(),
                deployment_repository=DeploymentRepository(),
            )

            async with AsyncSessionFactory() as session:
                canary = await service.create_canary_deployment(
                    session=session,
                    project_id=project_id,
                    model_name=MODEL_NAME,
                    model_version=CANARY_VERSION,
                    environment=DeploymentEnvironment.STAGING,
                    endpoint=CANARY_ENDPOINT,
                    canary_percentage=5,
                )

                promoted = (
                    await service.promote_canary_deployment(
                        session=session,
                        deployment_id=canary.id,
                    )
                )

                assert promoted.status == "production"
                assert promoted.environment == "production"
                assert promoted.traffic_percentage == 100
                assert promoted.model_version == CANARY_VERSION

                deployments = (
                    await service.deployment_repository.list_by_project(
                        session,
                        project_id,
                    )
                )

                stable = next(
                    deployment
                    for deployment in deployments
                    if deployment.model_version == STABLE_VERSION
                )

                assert stable.status == "staging"
                assert stable.traffic_percentage == 0
                assert (
                    promoted.traffic_percentage
                    + stable.traffic_percentage
                    == 100
                )

        asyncio.run(run_test())

    finally:
        cleanup_project(project_id)


def test_non_canary_deployment_cannot_be_promoted() -> None:
    """Only a CANARY deployment may enter promotion."""

    import asyncio

    project_id = create_test_project()

    try:
        asyncio.run(
            create_stable_deployment(project_id)
        )

        async def run_test() -> None:
            service = DeploymentService(
                project_repository=ProjectRepository(),
                deployment_repository=DeploymentRepository(),
            )

            async with AsyncSessionFactory() as session:
                deployments = (
                    await service.deployment_repository.list_by_project(
                        session,
                        project_id,
                    )
                )

                stable = deployments[0]

                with pytest.raises(ValueError, match="must be in canary"):
                    await service.promote_canary_deployment(
                        session=session,
                        deployment_id=stable.id,
                    )

        asyncio.run(run_test())

    finally:
        cleanup_project(project_id)


def test_rollback_canary_restores_stable_traffic() -> None:
    """Rollback before promotion restores stable traffic to 100%."""
    import asyncio

    project_id = create_test_project()

    try:
        asyncio.run(create_stable_deployment(project_id))

        async def run_test() -> None:
            service = DeploymentService(
                project_repository=ProjectRepository(),
                deployment_repository=DeploymentRepository(),
            )

            async with AsyncSessionFactory() as session:
                deployments = (
                    await service.deployment_repository.list_by_project(
                        session,
                        project_id,
                    )
                )

                stable_before = next(
                    item
                    for item in deployments
                    if item.model_version == STABLE_VERSION
                )

                canary = await service.create_canary_deployment(
                    session=session,
                    project_id=project_id,
                    model_name=MODEL_NAME,
                    model_version=CANARY_VERSION,
                    environment=DeploymentEnvironment.STAGING,
                    endpoint=CANARY_ENDPOINT,
                    canary_percentage=5,
                )

                rolled_back = (
                    await service.rollback_canary_deployment(
                        session=session,
                        deployment_id=canary.id,
                    )
                )

                stable = (
                    await service.deployment_repository.get_by_id(
                        session,
                        stable_before.id,
                    )
                )

                assert stable is not None
                assert stable.status == "staging"
                assert stable.traffic_percentage == 100

                assert rolled_back.status == "rolled_back"
                assert rolled_back.traffic_percentage == 0

                assert stable.traffic_percentage + (
                    rolled_back.traffic_percentage
                ) == 100

        asyncio.run(run_test())

    finally:
        cleanup_project(project_id)


def test_rollback_promoted_canary_restores_previous_production() -> None:
    """Rollback after promotion restores the previous stable model."""
    import asyncio

    project_id = create_test_project()

    try:
        asyncio.run(create_stable_deployment(project_id))

        async def run_test() -> None:
            service = DeploymentService(
                project_repository=ProjectRepository(),
                deployment_repository=DeploymentRepository(),
            )

            async with AsyncSessionFactory() as session:
                deployments = (
                    await service.deployment_repository.list_by_project(
                        session,
                        project_id,
                    )
                )

                stable_before = next(
                    item
                    for item in deployments
                    if item.model_version == STABLE_VERSION
                )

                canary = await service.create_canary_deployment(
                    session=session,
                    project_id=project_id,
                    model_name=MODEL_NAME,
                    model_version=CANARY_VERSION,
                    environment=DeploymentEnvironment.STAGING,
                    endpoint=CANARY_ENDPOINT,
                    canary_percentage=5,
                )

                promoted = await service.promote_canary_deployment(
                    session=session,
                    deployment_id=canary.id,
                )

                assert promoted.status == "production"
                assert promoted.traffic_percentage == 100

                rolled_back = (
                    await service.rollback_canary_deployment(
                        session=session,
                        deployment_id=canary.id,
                    )
                )

                stable = (
                    await service.deployment_repository.get_by_id(
                        session,
                        stable_before.id,
                    )
                )

                assert stable is not None
                assert stable.status == "production"
                assert stable.environment == "production"
                assert stable.traffic_percentage == 100

                assert rolled_back.status == "rolled_back"
                assert rolled_back.traffic_percentage == 0

                assert stable.traffic_percentage + (
                    rolled_back.traffic_percentage
                ) == 100

        asyncio.run(run_test())

    finally:
        cleanup_project(project_id)
