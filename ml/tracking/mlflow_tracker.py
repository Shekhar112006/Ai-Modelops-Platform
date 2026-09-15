from __future__ import annotations

import mlflow
import mlflow.sklearn


EXPERIMENT_NAME = "demo-classification"


def configure_tracking() -> None:
    """Configure the MLflow experiment used by the training pipeline."""

    mlflow.set_experiment(EXPERIMENT_NAME)


def start_run():
    """Start and return an MLflow tracking run."""

    return mlflow.start_run()