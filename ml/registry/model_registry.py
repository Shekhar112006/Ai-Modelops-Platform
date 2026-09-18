from __future__ import annotations

import mlflow
from mlflow import MlflowClient


REGISTERED_MODEL_NAME = "demo-classifier"


def get_registry_client() -> MlflowClient:
    """Return an MLflow client connected to the configured tracking server."""

    return MlflowClient()


def register_model_from_run(
    run_id: str,
    model_name: str = REGISTERED_MODEL_NAME,
    model_artifact_path: str = "model",
) -> object:
    """
    Register a model logged by a specific MLflow run.

    The run's artifact becomes a new version under the registered model.
    """

    model_uri = f"runs:/{run_id}/{model_artifact_path}"

    model_version = mlflow.register_model(
        model_uri=model_uri,
        name=model_name,
        tags={
            "validation_status": "passed",
            "registration_source": "automated-quality-gate",
        },
    )

    return model_version


def mark_as_candidate(
    model_name: str,
    model_version: str,
) -> None:
    """Assign the candidate alias to a registered model version."""

    client = get_registry_client()

    client.set_registered_model_alias(
        name=model_name,
        alias="candidate",
        version=model_version,
    )

    client.set_model_version_tag(
        name=model_name,
        version=model_version,
        key="lifecycle_status",
        value="candidate",
    )

def register_logged_model(
    model_id: str,
    model_name: str = REGISTERED_MODEL_NAME,
) -> object:
    """
    Register an MLflow 3 LoggedModel as a registered model version.
    """

    model_uri = f"models:/{model_id}"

    model_version = mlflow.register_model(
        model_uri=model_uri,
        name=model_name,
        tags={
            "validation_status": "passed",
            "registration_source": "automated-quality-gate",
        },
    )

    return model_version