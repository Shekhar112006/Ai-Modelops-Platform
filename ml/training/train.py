from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.training.evaluate import evaluate_classifier
from ml.training.preprocess import split_dataset
from ml.workloads.demo.dataset import (
    TARGET_COLUMN,
    generate_dataset,
)
import mlflow
import mlflow.sklearn

from ml.tracking.mlflow_tracker import configure_tracking


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "raw"
    / "demo_dataset.csv"
)

MODEL_DIR = PROJECT_ROOT / "models"

MODEL_PATH = MODEL_DIR / "model-v1.joblib"
METADATA_PATH = MODEL_DIR / "model-v1.json"


def build_model() -> Pipeline:
    """Build the reproducible preprocessing + model pipeline."""

    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )


def train() -> dict[str, object]:
    """Run the complete Model V1 training workflow with MLflow tracking."""

    configure_tracking()

    with mlflow.start_run() as run:
        print("=" * 60)
        print("AI ModelOps Platform - Model V1 Training")
        print("=" * 60)

        print("\n[1/6] Generating dataset...")
        dataset = generate_dataset(RAW_DATA_PATH)

        print(f"Dataset shape: {dataset.shape}")

        print("\n[2/6] Splitting dataset...")
        split = split_dataset(
            dataset=dataset,
            target_column=TARGET_COLUMN,
        )

        print(f"Training samples: {len(split.X_train)}")
        print(f"Testing samples:  {len(split.X_test)}")

        print("\n[3/6] Building model...")

        model = build_model()

        mlflow.log_params(
            {
                "algorithm": "LogisticRegression",
                "test_size": 0.2,
                "random_state": 42,
                "max_iter": 1000,
                "dataset_version": "D1",
            }
        )

        print("\n[4/6] Training...")
        model.fit(split.X_train, split.y_train)

        print("\n[5/6] Evaluating...")

        metrics = evaluate_classifier(
            model=model,
            X_test=split.X_test,
            y_test=split.y_test,
        )

        mlflow.log_metrics(metrics)

        print("\n[6/6] Logging model to MLflow...")

        mlflow.sklearn.log_model(
            sk_model=model,
            name="demo-classifier",
        )

        mlflow.set_tags(
            {
                "model_version": "v1",
                "workload": "demo-classification",
                "dataset_version": "D1",
                "pipeline_version": "v1",
            }
        )

        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        dump(model, MODEL_PATH)

        metadata = {
            "model_name": "demo-classifier",
            "model_version": "v1",
            "dataset": "demo_dataset.csv",
            "dataset_version": "D1",
            "algorithm": "LogisticRegression",
            "random_state": 42,
            "metrics": metrics,
            "mlflow_run_id": run.info.run_id,
        }

        METADATA_PATH.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        print("\n" + "=" * 60)
        print("MODEL RESULTS")
        print("=" * 60)

        for metric_name, value in metrics.items():
            print(f"{metric_name:10s}: {value:.4f}")

        print("\nMLflow Run ID:")
        print(run.info.run_id)

        print("\nModel saved to:")
        print(MODEL_PATH)

        print("\nMetadata saved to:")
        print(METADATA_PATH)

        return metadata


if __name__ == "__main__":
    train()