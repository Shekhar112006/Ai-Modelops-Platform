from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class ModelCandidate:
    """Definition of one model candidate."""

    name: str
    build: Callable[[], Pipeline]
    parameters: dict[str, object]


def build_logistic_regression() -> Pipeline:
    """Build the logistic regression candidate."""

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


def build_random_forest() -> Pipeline:
    """Build the random forest candidate."""

    return Pipeline(
        steps=[
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=200,
                    max_depth=10,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def build_gradient_boosting() -> Pipeline:
    """Build the gradient boosting candidate."""

    return Pipeline(
        steps=[
            (
                "classifier",
                GradientBoostingClassifier(
                    n_estimators=150,
                    learning_rate=0.05,
                    max_depth=3,
                    random_state=42,
                ),
            ),
        ]
    )


def get_model_candidates() -> list[ModelCandidate]:
    """Return all candidates evaluated by the training pipeline."""

    return [
        ModelCandidate(
            name="logistic_regression",
            build=build_logistic_regression,
            parameters={
                "algorithm": "LogisticRegression",
                "max_iter": 1000,
            },
        ),
        ModelCandidate(
            name="random_forest",
            build=build_random_forest,
            parameters={
                "algorithm": "RandomForestClassifier",
                "n_estimators": 200,
                "max_depth": 10,
            },
        ),
        ModelCandidate(
            name="gradient_boosting",
            build=build_gradient_boosting,
            parameters={
                "algorithm": "GradientBoostingClassifier",
                "n_estimators": 150,
                "learning_rate": 0.05,
                "max_depth": 3,
            },
        ),
    ]