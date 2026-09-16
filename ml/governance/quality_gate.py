from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityPolicy:
    """Rules a candidate model must satisfy before promotion."""

    minimum_f1: float = 0.85
    minimum_roc_auc: float = 0.90


@dataclass(frozen=True)
class QualityResult:
    """Result of evaluating one candidate against the quality policy."""

    passed: bool
    reasons: tuple[str, ...]


def evaluate_quality(
    metrics: dict[str, float],
    policy: QualityPolicy,
) -> QualityResult:
    """Evaluate a model candidate against the configured quality policy."""

    reasons: list[str] = []

    f1 = metrics.get("f1")
    roc_auc = metrics.get("roc_auc")

    if f1 is None:
        reasons.append("Missing required metric: f1.")
    elif f1 < policy.minimum_f1:
        reasons.append(
            f"F1 {f1:.4f} is below minimum "
            f"{policy.minimum_f1:.4f}."
        )

    if roc_auc is None:
        reasons.append("Missing required metric: roc_auc.")
    elif roc_auc < policy.minimum_roc_auc:
        reasons.append(
            f"ROC-AUC {roc_auc:.4f} is below minimum "
            f"{policy.minimum_roc_auc:.4f}."
        )

    return QualityResult(
        passed=not reasons,
        reasons=tuple(reasons),
    )