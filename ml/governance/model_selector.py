from __future__ import annotations

from dataclasses import dataclass

from ml.governance.quality_gate import (
    QualityPolicy,
    QualityResult,
    evaluate_quality,
)


@dataclass(frozen=True)
class CandidateEvaluation:
    """Candidate model together with its quality-gate result."""

    candidate: str
    run_id: str
    metrics: dict[str, float]
    quality: QualityResult


def evaluate_candidates(
    candidates: list[dict[str, object]],
    policy: QualityPolicy,
) -> list[CandidateEvaluation]:
    """Evaluate all candidates against the same quality policy."""

    evaluations: list[CandidateEvaluation] = []

    for candidate in candidates:
        metrics = {
            key: float(value)
            for key, value in candidate.items()
            if key in {
                "accuracy",
                "precision",
                "recall",
                "f1",
                "roc_auc",
            }
        }

        quality = evaluate_quality(
            metrics=metrics,
            policy=policy,
        )

        evaluations.append(
            CandidateEvaluation(
                candidate=str(candidate["candidate"]),
                run_id=str(candidate["run_id"]),
                metrics=metrics,
                quality=quality,
            )
        )

    return evaluations


def select_best_candidate(
    evaluations: list[CandidateEvaluation],
) -> CandidateEvaluation:
    """
    Select the highest-F1 candidate among candidates that
    passed the quality gate.
    """

    eligible = [
        evaluation
        for evaluation in evaluations
        if evaluation.quality.passed
    ]

    if not eligible:
        raise ValueError(
            "No candidate model passed the quality gate."
        )

    return max(
        eligible,
        key=lambda evaluation: evaluation.metrics["f1"],
    )