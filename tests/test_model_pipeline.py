from pathlib import Path

from ml.training.evaluate import evaluate_classifier
from ml.training.preprocess import split_dataset
from ml.workloads.demo.dataset import (
    TARGET_COLUMN,
    generate_dataset,
)
from ml.training.train import build_model


def test_dataset_generation(tmp_path: Path) -> None:
    """Dataset generation should produce the expected schema."""

    output_path = tmp_path / "dataset.csv"

    dataset = generate_dataset(
        output_path=output_path,
        n_samples=1000,
    )

    assert output_path.exists()
    assert len(dataset) == 1000
    assert TARGET_COLUMN in dataset.columns


def test_training_pipeline() -> None:
    """Model should train and produce valid evaluation metrics."""

    dataset = generate_dataset(
        output_path=Path("/tmp/modelops-test-dataset.csv"),
        n_samples=1000,
    )

    split = split_dataset(
        dataset=dataset,
        target_column=TARGET_COLUMN,
    )

    model = build_model()

    model.fit(
        split.X_train,
        split.y_train,
    )

    metrics = evaluate_classifier(
        model=model,
        X_test=split.X_test,
        y_test=split.y_test,
    )

    assert metrics["accuracy"] >= 0.80
    assert metrics["f1"] >= 0.80