"""Statistical feature-distribution drift detection."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


class DriftDetector:
    """Compare incoming feature distributions with a reference dataset."""

    def __init__(
        self,
        reference_data: pd.DataFrame,
        feature_columns: list[str],
        significance_level: float = 0.05,
        minimum_samples: int = 20,
    ) -> None:
        if not 0 < significance_level < 1:
            raise ValueError("significance_level must be between 0 and 1.")

        if minimum_samples < 2:
            raise ValueError("minimum_samples must be at least 2.")

        missing = [
            column
            for column in feature_columns
            if column not in reference_data.columns
        ]
        if missing:
            raise ValueError(
                f"Reference dataset is missing features: {missing}"
            )

        self.feature_columns = feature_columns
        self.significance_level = significance_level
        self.minimum_samples = minimum_samples
        self.reference = reference_data[feature_columns].to_numpy(
            dtype=float
        )

        if not np.isfinite(self.reference).all():
            raise ValueError("Reference data contains non-finite values.")

    def detect(
        self,
        current_data: pd.DataFrame | list[list[float]],
    ) -> dict[str, Any]:
        """Compare each current feature distribution against its baseline."""

        if isinstance(current_data, pd.DataFrame):
            missing = [
                column
                for column in self.feature_columns
                if column not in current_data.columns
            ]
            if missing:
                raise ValueError(
                    f"Current dataset is missing features: {missing}"
                )
            current = current_data[self.feature_columns].to_numpy(
                dtype=float
            )
        else:
            current = np.asarray(current_data, dtype=float)

        if current.ndim != 2:
            raise ValueError("Current data must be a two-dimensional batch.")

        if current.shape[1] != len(self.feature_columns):
            raise ValueError(
                f"Expected {len(self.feature_columns)} features; "
                f"received {current.shape[1]}."
            )

        if current.shape[0] < self.minimum_samples:
            raise ValueError(
                f"At least {self.minimum_samples} samples are required."
            )

        if not np.isfinite(current).all():
            raise ValueError("Current data contains non-finite values.")

        feature_results: dict[str, dict[str, float | bool]] = {}

        for index, feature in enumerate(self.feature_columns):
            statistic, p_value = ks_2samp(
                self.reference[:, index],
                current[:, index],
            )

            feature_results[feature] = {
                "statistic": float(statistic),
                "p_value": float(p_value),
                "drift_detected": bool(
                    p_value < (self.significance_level / len(self.feature_columns))
                ),
            }

        drifted_features = [
            name
            for name, result in feature_results.items()
            if result["drift_detected"]
        ]

        return {
            "drift_detected": bool(drifted_features),
            "reference_samples": int(self.reference.shape[0]),
            "current_samples": int(current.shape[0]),
            "features_checked": len(self.feature_columns),
            "drifted_feature_count": len(drifted_features),
            "drifted_features": drifted_features,
            "significance_level": self.significance_level,
            "feature_results": feature_results,
        }
