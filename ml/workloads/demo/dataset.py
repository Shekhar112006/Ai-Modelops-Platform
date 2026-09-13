from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.datasets import make_classification


FEATURE_COLUMNS = [
    "feature_01",
    "feature_02",
    "feature_03",
    "feature_04",
    "feature_05",
    "feature_06",
    "feature_07",
    "feature_08",
    "feature_09",
    "feature_10",
]

TARGET_COLUMN = "target"


def generate_dataset(
    output_path: Path,
    n_samples: int = 5000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate a deterministic classification dataset and save it as CSV."""

    X, y = make_classification(
        n_samples=n_samples,
        n_features=len(FEATURE_COLUMNS),
        n_informative=6,
        n_redundant=2,
        n_repeated=0,
        n_classes=2,
        class_sep=1.5,
        random_state=random_state,
    )

    dataset = pd.DataFrame(X, columns=FEATURE_COLUMNS)
    dataset[TARGET_COLUMN] = y

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)

    return dataset