from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import mlflow.sklearn
from joblib import dump

from ml.training.candidates import get_model_candidates
from ml.training.evaluate import evaluate_classifier
from ml.training.preprocess import split_dataset
from ml.workloads.demo.dataset import (
    TARGET_COLUMN,
    generate_dataset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "raw"
    / "demo_dataset.csv"
)

MODEL_DIR = PROJECT_ROOT / "models" / "candidates"

EXPERIMENT_NAME = "demo-classification"


def train_candidates() -> list[dict[str, object]]:
    """Train and track every configured model candidate."""

    mlflow.set_experiment(EXPERIMENT_NAME)

    print("=" * 70)
    print("AI ModelOps Platform - Candidate Model Training")
    print("=" * 70)

    print("\n[1/4] Preparing dataset...")

    dataset = generate_dataset(
        output_path=RAW_DATA_PATH,
        n_samples=5000,
        random_state=42,
    )

    print(f"Dataset shape: {dataset.shape}")

    print("\n[2/4] Creating train/test split...")

    split = split_dataset(
        dataset=dataset,
        target_column=TARGET_COLUMN,
    )

    print(f"Training samples: {len(split.X_train)}")
    print(f"Testing samples:  {len(split.X_test)}")

    candidates = get_model_candidates()
    results: list[dict[str, object]] = []

    print(f"\n[3/4] Training {len(candidates)} candidates...")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for index, candidate in enumerate(candidates, start=1):
        print("\n" + "-" * 70)
        print(
            f"Candidate {index}/{len(candidates)}: "
            f"{candidate.name}"
        )
        print("-" * 70)

        model = candidate.build()

        with mlflow.start_run(
            run_name=candidate.name,
        ) as run:
            mlflow.log_params(candidate.parameters)

            mlflow.log_params(
                {
                    "dataset_version": "D1",
                    "test_size": 0.2,
                    "random_state": 42,
                }
            )

            print("Training...")

            model.fit(
                split.X_train,
                split.y_train,
            )

            metrics = evaluate_classifier(
                model=model,
                X_test=split.X_test,
                y_test=split.y_test,
            )

            mlflow.log_metrics(metrics)

            mlflow.set_tags(
                {
                    "workload": "demo-classification",
                    "model_candidate": candidate.name,
                    "dataset_version": "D1",
                    "pipeline_version": "v2",
                }
            )

            model_info = mlflow.sklearn.log_model(
                sk_model=model,
                name="model",
            )

            local_model_path = (
                MODEL_DIR / f"{candidate.name}.joblib"
            )

            dump(model, local_model_path)

            metadata = {
                "candidate": candidate.name,
                "run_id": run.info.run_id,
                "model_id": model_info.model_id,
                "metrics": metrics,
                "dataset_version": "D1",
                "created_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "model_path": str(local_model_path),
            }

            metadata_path = (
                MODEL_DIR / f"{candidate.name}.json"
            )

            metadata_path.write_text(
                json.dumps(metadata, indent=2),
                encoding="utf-8",
            )

            result = {
                "candidate": candidate.name,
                "run_id": run.info.run_id,
                "model_id": model_info.model_id,
                **metrics,
            }

            results.append(result)

            print("\nResults:")

            for metric_name, value in metrics.items():
                print(
                    f"{metric_name:10s}: {value:.4f}"
                )

            print(f"Run ID: {run.info.run_id}")

    print("\n[4/4] Candidate training complete.")

    print("\n" + "=" * 70)
    print("CANDIDATE SUMMARY")
    print("=" * 70)

    for result in results:
        print(
            f"{result['candidate']:22s} "
            f"F1={result['f1']:.4f} "
            f"ROC-AUC={result['roc_auc']:.4f}"
        )

    return results


if __name__ == "__main__":
    train_candidates()