from __future__ import annotations

from uuid import UUID

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.deployment import (
    DeploymentEnvironment,
    DeploymentStatus,
    validate_deployment_transition,
)
from backend.app.models.deployment import Deployment
from backend.app.repositories.deployment_repository import (
    DeploymentRepository,
)
from backend.app.repositories.project_repository import (
    ProjectRepository,
)


class DeploymentProjectNotFoundError(Exception):
    """Raised when the target project does not exist."""


class DeploymentModelNotFoundError(Exception):
    """Raised when the requested MLflow model version does not exist."""


class DeploymentModelNotEligibleError(Exception):
    """Raised when a model version has not passed validation."""


class DeploymentNotFoundError(Exception):
    """Raised when a deployment does not exist."""


class DeploymentService:
    """Business logic for model deployment operations."""

    def __init__(
        self,
        project_repository: ProjectRepository | None = None,
        deployment_repository: DeploymentRepository | None = None,
        mlflow_client: MlflowClient | None = None,
    ) -> None:
        self.project_repository = (
            project_repository
            or ProjectRepository()
        )

        self.deployment_repository = (
            deployment_repository
            or DeploymentRepository()
        )

        self.mlflow_client = (
            mlflow_client
            or MlflowClient()
        )

    def _get_model_version(
        self,
        model_name: str,
        model_version: str,
    ):
        """Fetch a model version from the MLflow registry."""

        try:
            return self.mlflow_client.get_model_version(
                name=model_name,
                version=model_version,
            )

        except MlflowException as exc:
            raise DeploymentModelNotFoundError(
                f"MLflow model '{model_name}' version "
                f"'{model_version}' was not found."
            ) from exc

    async def create_deployment(
        self,
        session: AsyncSession,
        project_id: UUID,
        model_name: str,
        model_version: str,
        environment: DeploymentEnvironment,
    ) -> Deployment:
        """
        Create a deployment after validating project and model eligibility.

        New deployments always begin in the CREATED state.
        """

        project = await self.project_repository.get_by_id(
            session,
            project_id,
        )

        if project is None:
            raise DeploymentProjectNotFoundError(
                f"Project '{project_id}' was not found."
            )

        model_version_info = self._get_model_version(
            model_name=model_name,
            model_version=model_version,
        )

        validation_status = model_version_info.tags.get(
            "validation_status"
        )

        if validation_status != "passed":
            raise DeploymentModelNotEligibleError(
                f"Model '{model_name}' version "
                f"'{model_version}' is not eligible for deployment. "
                f"validation_status={validation_status!r}."
            )

        deployment = Deployment(
            project_id=project_id,
            model_name=model_name,
            model_version=model_version,
            environment=environment.value,
            status=DeploymentStatus.CREATED.value,
            traffic_percentage=0,
        )

        deployment = await self.deployment_repository.create(
            session,
            deployment,
        )

        await session.commit()
        await session.refresh(deployment)

        return deployment

    async def transition_deployment(
        self,
        session: AsyncSession,
        deployment_id: UUID,
        target_status: DeploymentStatus,
    ) -> Deployment:
        """Move a deployment through a valid lifecycle transition."""

        deployment = await self.deployment_repository.get_by_id(
            session,
            deployment_id,
        )

        if deployment is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' was not found."
            )

        current_status = DeploymentStatus(
            deployment.status
        )

        validate_deployment_transition(
            current=current_status,
            target=target_status,
        )

        await self.deployment_repository.update_status(
            session=session,
            deployment_id=deployment_id,
            status=target_status.value,
        )

        await session.commit()

        updated_deployment = (
            await self.deployment_repository.get_by_id(
                session,
                deployment_id,
            )
        )

        if updated_deployment is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' disappeared "
                "after status update."
            )

        return updated_deployment

    async def get_deployment(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> Deployment:
        """Return a deployment or raise a domain-level error."""

        deployment = await self.deployment_repository.get_by_id(
            session,
            deployment_id,
        )

        if deployment is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' was not found."
            )

        return deployment

    async def list_project_deployments(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> list[Deployment]:
        """Return all deployments belonging to a project."""

        return await self.deployment_repository.list_by_project(
            session,
            project_id,
        )
