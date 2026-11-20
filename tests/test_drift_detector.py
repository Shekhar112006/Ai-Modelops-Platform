from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.drift.detector import DriftDetector


FEATURES = [f"feature_{index:02d}" for index in range(1, 11)]


@pytest.fixture
def detector() -> DriftDetector:
    rng = np.random.default_rng(42)
    reference = pd.DataFrame(
        rng.normal(size=(1000, 10)),
        columns=FEATURES,
    )
    return DriftDetector(reference, FEATURES)


def test_similar_distribution_has_no_drift(
    detector: DriftDetector,
) -> None:
    rng = np.random.default_rng(123)
    current = rng.normal(size=(500, 10))

    report = detector.detect(current)

    assert report["drift_detected"] is False
    assert report["drifted_feature_count"] == 0
    assert report["current_samples"] == 500


def test_shifted_feature_is_detected(
    detector: DriftDetector,
) -> None:
    rng = np.random.default_rng(123)
    current = rng.normal(size=(500, 10))
    current[:, 0] += 5.0

    report = detector.detect(current)

    assert report["drift_detected"] is True
    assert "feature_01" in report["drifted_features"]
    assert (
        report["feature_results"]["feature_01"]["p_value"]
        < 0.05
    )


def test_rejects_insufficient_samples(
    detector: DriftDetector,
) -> None:
    with pytest.raises(ValueError, match="At least 20 samples"):
        detector.detect(np.zeros((10, 10)))


def test_rejects_wrong_feature_count(
    detector: DriftDetector,
) -> None:
    with pytest.raises(ValueError, match="Expected 10 features"):
        detector.detect(np.zeros((100, 9)))


def test_rejects_non_finite_values(
    detector: DriftDetector,
) -> None:
    current = np.zeros((100, 10))
    current[0, 0] = np.nan

    with pytest.raises(ValueError, match="non-finite"):
        detector.detect(current)
