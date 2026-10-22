from __future__ import annotations

from typing import Any

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from backend.app.core.config import settings


class RegistryModelNotFoundError(Exception):
    """Raised when a registered model does not exist."""


class RegistryVersionNotFoundError(Exception):
    """Raised when a registered model version does not exist."""


class RegistryUnavailableError(Exception):
    """Raised when the MLflow registry cannot be accessed."""


class RegistryService:
    """Read-only service for querying the MLflow Model Registry."""

    def __init__(
        self,
        mlflow_client: MlflowClient | None = None,
    ) -> None:
        self.mlflow_client = mlflow_client or MlflowClient(
            tracking_uri=settings.mlflow_tracking_uri,
        )

    @staticmethod
    def _version_to_dict(version: Any) -> dict[str, Any]:
        """Convert an MLflow model version to an API-friendly dictionary."""

        return {
            "name": version.name,
            "version": str(version.version),
            "status": version.status,
            "run_id": version.run_id,
            "source": version.source,
            "description": version.description,
            "tags": dict(version.tags or {}),
            "creation_timestamp": version.creation_timestamp,
            "last_updated_timestamp": version.last_updated_timestamp,
        }

    def list_models(self) -> list[dict[str, Any]]:
        """List registered models, including their aliases and tags."""

        try:
            models = self.mlflow_client.search_registered_models()

            return [
                {
                    "name": model.name,
                    "description": model.description,
                    "tags": dict(model.tags or {}),
                    "aliases": dict(model.aliases or {}),
                    "latest_versions": [
                        self._version_to_dict(version)
                        for version in (model.latest_versions or [])
                    ],
                }
                for model in models
            ]

        except MlflowException as exc:
            raise RegistryUnavailableError(
                "Unable to retrieve registered models from MLflow."
            ) from exc

    def list_versions(
        self,
        model_name: str,
    ) -> list[dict[str, Any]]:
        """List all registered versions of a model."""

        try:
            model = self.mlflow_client.get_registered_model(model_name)

            versions = self.mlflow_client.search_model_versions(
                filter_string=f"name='{model.name}'",
            )

            return [
                self._version_to_dict(version)
                for version in sorted(
                    versions,
                    key=lambda item: int(item.version),
                    reverse=True,
                )
            ]

        except MlflowException as exc:
            if self._is_not_found(exc):
                raise RegistryModelNotFoundError(
                    f"Registered model '{model_name}' was not found."
                ) from exc

            raise RegistryUnavailableError(
                "Unable to retrieve model versions from MLflow."
            ) from exc

    def get_version(
        self,
        model_name: str,
        version: str,
    ) -> dict[str, Any]:
        """Retrieve one registered model version."""

        try:
            model_version = self.mlflow_client.get_model_version(
                name=model_name,
                version=version,
            )

            return self._version_to_dict(model_version)

        except MlflowException as exc:
            if self._is_not_found(exc):
                raise RegistryVersionNotFoundError(
                    f"Model '{model_name}' version '{version}' was not found."
                ) from exc

            raise RegistryUnavailableError(
                "Unable to retrieve the requested model version from MLflow."
            ) from exc

    @staticmethod
    def _is_not_found(exc: MlflowException) -> bool:
        """Identify MLflow errors that indicate a missing registry resource."""

        message = str(exc).lower()

        return any(
            phrase in message
            for phrase in (
                "does not exist",
                "not found",
                "resource_does_not_exist",
            )
        )
