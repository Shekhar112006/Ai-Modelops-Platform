from __future__ import annotations

import tempfile
from typing import Sequence

import mlflow
import pandas as pd

from ml.workloads.demo.dataset import FEATURE_COLUMNS


class ModelInference:
    """Load a registered MLflow model and perform predictions."""

    def __init__(
        self,
        model_name: str,
        model_version: str,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self.model_uri = (
            f"models:/{model_name}/{model_version}"
        )

        # MLflow may create registered-model metadata while
        # downloading a registered model, so keep the downloaded
        # serving copy in a writable temporary directory.
        self._model_dir = tempfile.TemporaryDirectory(
            prefix="mlflow-model-"
        )

        self.model = mlflow.pyfunc.load_model(
            self.model_uri,
            dst_path=self._model_dir.name,
        )

    def predict(
        self,
        features: Sequence[float],
    ) -> list[object]:
        """Run inference for one or more feature vectors."""

        if len(features) != len(FEATURE_COLUMNS):
            raise ValueError(
                f"Expected {len(FEATURE_COLUMNS)} features, "
                f"received {len(features)}."
            )

        dataframe = pd.DataFrame(
            [list(features)],
            columns=FEATURE_COLUMNS,
        )

        predictions = self.model.predict(dataframe)

        return predictions.tolist()
