from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import train_test_split


@dataclass(frozen=True)
class DatasetSplit:
    """Container for the training and testing datasets."""

    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


def split_dataset(
    dataset: pd.DataFrame,
    target_column: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> DatasetSplit:
    """Separate features from target and create a reproducible train/test split."""

    if target_column not in dataset.columns:
        raise ValueError(f"Target column '{target_column}' does not exist.")

    X = dataset.drop(columns=[target_column])
    y = dataset[target_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    return DatasetSplit(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
    )