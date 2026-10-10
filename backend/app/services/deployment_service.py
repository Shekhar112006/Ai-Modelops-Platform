from __future__ import annotations

from uuid import UUID

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.deployment import (
    DeploymentEnvironment,
    DeploymentStatus,
    validate_canary_traffic,
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

    async def create_canary_deployment(
        self,
        session: AsyncSession,
        project_id: UUID,
        model_name: str,
        model_version: str,
        environment: DeploymentEnvironment,
        endpoint: str,
        canary_percentage: int,
    ) -> Deployment:
        """
        Create a canary deployment and reduce the current stable
        deployment by the canary traffic percentage.
        """

        validate_canary_traffic(canary_percentage)

        if not endpoint.strip():
            raise ValueError(
                "Model serving endpoint cannot be empty."
            )

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

        active_deployments = (
            await self.deployment_repository.list_active_by_project(
                session=session,
                project_id=project_id,
                environment=environment.value,
            )
        )

        if not active_deployments:
            raise DeploymentNotFoundError(
                "No active deployment exists to receive "
                "canary traffic."
            )

        total_traffic = sum(
            deployment.traffic_percentage
            for deployment in active_deployments
        )

        if total_traffic != 100:
            raise ValueError(
                f"Active deployment traffic must total 100%. "
                f"Current total is {total_traffic}%."
            )

        stable_candidates = [
            deployment
            for deployment in active_deployments
            if deployment.status
            in {
                DeploymentStatus.STAGING.value,
                DeploymentStatus.PRODUCTION.value,
            }
            and deployment.traffic_percentage > 0
        ]

        if not stable_candidates:
            raise ValueError(
                "No stable deployment with traffic was found."
            )

        stable = max(
            stable_candidates,
            key=lambda deployment: deployment.traffic_percentage,
        )

        if (
            stable.model_name == model_name
            and stable.model_version == model_version
        ):
            raise ValueError(
                "Canary model must differ from the stable model."
            )

        new_stable_percentage = (
            stable.traffic_percentage
            - canary_percentage
        )

        if new_stable_percentage < 1:
            raise ValueError(
                "Canary percentage is too large for the "
                "current stable allocation."
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

        current_status = DeploymentStatus.CREATED

        required_transitions = [
            DeploymentStatus.VALIDATING,
            DeploymentStatus.APPROVED,
            DeploymentStatus.STAGING,
            DeploymentStatus.CANARY,
        ]

        for target_status in required_transitions:
            validate_deployment_transition(
                current=current_status,
                target=target_status,
            )

            await self.deployment_repository.update_status(
                session=session,
                deployment_id=deployment.id,
                status=target_status.value,
            )

            current_status = target_status

        await self.deployment_repository.update_endpoint(
            session=session,
            deployment_id=stable.id,
            endpoint=stable.model_endpoint or "",
            traffic_percentage=new_stable_percentage,
        )

        await self.deployment_repository.update_endpoint(
            session=session,
            deployment_id=deployment.id,
            endpoint=endpoint,
            traffic_percentage=canary_percentage,
        )

        await session.commit()
        await session.refresh(deployment)

        return deployment

    async def promote_canary_deployment(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> Deployment:
        """
        Promote a canary deployment to production.

        The canary receives 100% traffic while the previous
        stable deployment remains available with 0% traffic.
        """

        canary = await self.deployment_repository.get_by_id(
            session,
            deployment_id,
        )

        if canary is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' was not found."
            )

        if canary.status != DeploymentStatus.CANARY.value:
            raise ValueError(
                f"Deployment '{deployment_id}' must be in "
                f"canary state before promotion. "
                f"Current state={canary.status!r}."
            )

        active_deployments = (
            await self.deployment_repository.list_active_by_project(
                session=session,
                project_id=canary.project_id,
                environment=canary.environment,
            )
        )

        stable_candidates = [
            deployment
            for deployment in active_deployments
            if deployment.id != canary.id
            and deployment.traffic_percentage > 0
            and deployment.status
            in {
                DeploymentStatus.STAGING.value,
                DeploymentStatus.PRODUCTION.value,
            }
        ]

        if not stable_candidates:
            raise ValueError(
                "No active stable deployment was found "
                "for canary promotion."
            )

        total_traffic = sum(
            deployment.traffic_percentage
            for deployment in active_deployments
        )

        if total_traffic != 100:
            raise ValueError(
                f"Active deployment traffic must total 100%. "
                f"Current total is {total_traffic}%."
            )

        validate_deployment_transition(
            current=DeploymentStatus.CANARY,
            target=DeploymentStatus.PROMOTING,
        )

        await self.deployment_repository.update_status(
            session=session,
            deployment_id=canary.id,
            status=DeploymentStatus.PROMOTING.value,
        )

        for stable in stable_candidates:
            await self.deployment_repository.update_endpoint(
                session=session,
                deployment_id=stable.id,
                endpoint=stable.model_endpoint or "",
                traffic_percentage=0,
            )

        validate_deployment_transition(
            current=DeploymentStatus.PROMOTING,
            target=DeploymentStatus.PRODUCTION,
        )

        await self.deployment_repository.update_environment(
            session=session,
            deployment_id=canary.id,
            environment=DeploymentEnvironment.PRODUCTION.value,
        )

        await self.deployment_repository.update_status(
            session=session,
            deployment_id=canary.id,
            status=DeploymentStatus.PRODUCTION.value,
        )

        await self.deployment_repository.update_endpoint(
            session=session,
            deployment_id=canary.id,
            endpoint=canary.model_endpoint or "",
            traffic_percentage=100,
        )

        await session.commit()

        promoted = (
            await self.deployment_repository.get_by_id(
                session,
                canary.id,
            )
        )

        if promoted is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' disappeared "
                "after promotion."
            )

        return promoted

    async def rollback_canary_deployment(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> Deployment:
        """
        Roll back a canary or promoted deployment.

        Before promotion:
            Restore the stable staging deployment to 100% traffic.

        After promotion:
            Restore the previous stable deployment to production
            with 100% traffic.

        In both cases, mark the failed deployment as rolled_back.
        """

        deployment = await self.deployment_repository.get_by_id(
            session,
            deployment_id,
        )

        if deployment is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' was not found."
            )

        current_status = DeploymentStatus(deployment.status)

        rollbackable_statuses = {
            DeploymentStatus.CANARY,
            DeploymentStatus.PRODUCTION,
        }

        if current_status not in rollbackable_statuses:
            raise ValueError(
                f"Deployment '{deployment_id}' must be in "
                "canary or production state before rollback. "
                f"Current state={deployment.status!r}."
            )

        project_deployments = (
            await self.deployment_repository.list_by_project(
                session,
                deployment.project_id,
            )
        )

        active_statuses = {
            DeploymentStatus.STAGING.value,
            DeploymentStatus.CANARY.value,
            DeploymentStatus.PROMOTING.value,
            DeploymentStatus.PRODUCTION.value,
        }

        active_in_current_environment = [
            item
            for item in project_deployments
            if item.environment == deployment.environment
            and item.status in active_statuses
        ]

        total_traffic = sum(
            item.traffic_percentage
            for item in active_in_current_environment
        )

        if total_traffic != 100:
            raise ValueError(
                "Active deployment traffic must total 100% "
                "before rollback. "
                f"Current total is {total_traffic}%."
            )

        if current_status == DeploymentStatus.CANARY:
            stable_candidates = [
                item
                for item in active_in_current_environment
                if item.id != deployment.id
                and item.status
                in {
                    DeploymentStatus.STAGING.value,
                    DeploymentStatus.PRODUCTION.value,
                }
                and item.traffic_percentage > 0
                and bool(item.model_endpoint)
            ]

        else:
            stable_candidates = [
                item
                for item in project_deployments
                if item.id != deployment.id
                and item.environment
                == DeploymentEnvironment.STAGING.value
                and item.status == DeploymentStatus.STAGING.value
                and item.traffic_percentage == 0
                and bool(item.model_endpoint)
            ]

        if len(stable_candidates) != 1:
            raise ValueError(
                "Rollback requires exactly one identifiable "
                "stable deployment. "
                f"Found {len(stable_candidates)} candidates."
            )

        stable = stable_candidates[0]

        validate_deployment_transition(
            current=current_status,
            target=DeploymentStatus.ROLLBACK,
        )

        validate_deployment_transition(
            current=DeploymentStatus.ROLLBACK,
            target=DeploymentStatus.ROLLED_BACK,
        )

        if current_status == DeploymentStatus.PRODUCTION:
            validate_deployment_transition(
                current=DeploymentStatus.STAGING,
                target=DeploymentStatus.PRODUCTION,
            )

        # Mark the failed deployment as entering rollback.
        await self.deployment_repository.update_status(
            session=session,
            deployment_id=deployment.id,
            status=DeploymentStatus.ROLLBACK.value,
        )

        # Remove all traffic from the failed deployment.
        await self.deployment_repository.update_endpoint(
            session=session,
            deployment_id=deployment.id,
            endpoint=deployment.model_endpoint or "",
            traffic_percentage=0,
        )

        if current_status == DeploymentStatus.CANARY:
            # The stable staging deployment keeps its current state.
            await self.deployment_repository.update_endpoint(
                session=session,
                deployment_id=stable.id,
                endpoint=stable.model_endpoint or "",
                traffic_percentage=100,
            )

        else:
            # Restore the previous stable deployment to production.
            await self.deployment_repository.update_environment(
                session=session,
                deployment_id=stable.id,
                environment=DeploymentEnvironment.PRODUCTION.value,
            )

            await self.deployment_repository.update_status(
                session=session,
                deployment_id=stable.id,
                status=DeploymentStatus.PRODUCTION.value,
            )

            await self.deployment_repository.update_endpoint(
                session=session,
                deployment_id=stable.id,
                endpoint=stable.model_endpoint or "",
                traffic_percentage=100,
            )

        # Complete the failed deployment's rollback lifecycle.
        await self.deployment_repository.update_status(
            session=session,
            deployment_id=deployment.id,
            status=DeploymentStatus.ROLLED_BACK.value,
        )

        await session.commit()

        rolled_back = await self.deployment_repository.get_by_id(
            session,
            deployment.id,
        )

        if rolled_back is None:
            raise DeploymentNotFoundError(
                f"Deployment '{deployment_id}' disappeared "
                "after rollback."
            )

        return rolled_back

    async def activate_staging_deployment(
        self,
        session: AsyncSession,
        deployment_id: UUID,
        endpoint: str,
    ) -> Deployment:
        """
        Move a deployment through the controlled staging lifecycle
        and attach its model-serving endpoint.
        """

        if not endpoint.strip():
            raise ValueError(
                "Model serving endpoint cannot be empty."
            )

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

        required_transitions = [
            DeploymentStatus.VALIDATING,
            DeploymentStatus.APPROVED,
            DeploymentStatus.STAGING,
        ]

        for target_status in required_transitions:
            validate_deployment_transition(
                current=current_status,
                target=target_status,
            )

            await self.deployment_repository.update_status(
                session=session,
                deployment_id=deployment_id,
                status=target_status.value,
            )

            current_status = target_status

        await self.deployment_repository.update_endpoint(
            session=session,
            deployment_id=deployment_id,
            endpoint=endpoint,
            traffic_percentage=100,
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
                "after activation."
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
