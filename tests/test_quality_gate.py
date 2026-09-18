from ml.governance.model_selector import (
    evaluate_candidates,
    select_best_candidate,
)
from ml.governance.quality_gate import QualityPolicy


def test_quality_gate_rejects_weak_model() -> None:
    """A candidate below the required metrics must be rejected."""

    policy = QualityPolicy(
        minimum_f1=0.90,
        minimum_roc_auc=0.90,
    )

    candidates = [
        {
            "candidate": "weak-model",
            "run_id": "run-1",
            "model_id": "model-1",
            "f1": 0.86,
            "roc_auc": 0.92,
        }
    ]

    evaluations = evaluate_candidates(
        candidates=candidates,
        policy=policy,
    )

    assert evaluations[0].quality.passed is False


def test_quality_gate_accepts_good_model() -> None:
    """A candidate meeting all required metrics must pass."""

    policy = QualityPolicy(
        minimum_f1=0.90,
        minimum_roc_auc=0.90,
    )

    candidates = [
        {
            "candidate": "good-model",
            "run_id": "run-2",
            "model_id": "model-2",
            "f1": 0.93,
            "roc_auc": 0.95,
        }
    ]

    evaluations = evaluate_candidates(
        candidates=candidates,
        policy=policy,
    )

    assert evaluations[0].quality.passed is True


def test_selector_chooses_best_eligible_model() -> None:
    """The selector must choose the highest-F1 eligible candidate."""

    policy = QualityPolicy(
        minimum_f1=0.90,
        minimum_roc_auc=0.90,
    )

    candidates = [
            {
                "candidate": "model-a",
                "run_id": "run-a",
                "model_id": "model-a-id",
                "f1": 0.88,
                "roc_auc": 0.95,
            },
            {
                "candidate": "model-b",
                "run_id": "run-b",
                "model_id": "model-b-id",
                "f1": 0.91,
                "roc_auc": 0.93,
            },
            {
                "candidate": "model-c",
                "run_id": "run-c",
                "model_id": "model-c-id",
                "f1": 0.94,
                "roc_auc": 0.96,
            },
        ]

    evaluations = evaluate_candidates(
        candidates=candidates,
        policy=policy,
    )

    selected = select_best_candidate(evaluations)

    assert selected.candidate == "model-c"