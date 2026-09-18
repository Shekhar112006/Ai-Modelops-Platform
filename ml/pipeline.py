from __future__ import annotations

from ml.governance.model_selector import (
    evaluate_candidates,
    select_best_candidate,
)
from ml.governance.quality_gate import QualityPolicy
from ml.registry.model_registry import (
    mark_as_candidate,
    register_logged_model,
)
from ml.training.train_candidates import train_candidates


def run_model_selection_pipeline() -> None:
    """Train candidates, apply the quality gate, and register the winner."""

    print("=" * 70)
    print("AI ModelOps - Automated Model Selection Pipeline")
    print("=" * 70)

    candidates = train_candidates()

    policy = QualityPolicy(
        minimum_f1=0.90,
        minimum_roc_auc=0.90,
    )

    print("\nApplying quality gate...")

    evaluations = evaluate_candidates(
        candidates=candidates,
        policy=policy,
    )

    for evaluation in evaluations:
        status = "PASS" if evaluation.quality.passed else "REJECT"

        print(
            f"{evaluation.candidate:22s} "
            f"F1={evaluation.metrics.get('f1', 0):.4f} "
            f"→ {status}"
        )

        if not evaluation.quality.passed:
            for reason in evaluation.quality.reasons:
                print(f"    Reason: {reason}")

    selected = select_best_candidate(evaluations)

    print("\n" + "=" * 70)
    print("SELECTED MODEL")
    print("=" * 70)

    print(f"Candidate: {selected.candidate}")
    print(f"Run ID:    {selected.run_id}")
    print(f"F1:        {selected.metrics['f1']:.4f}")
    print(f"ROC-AUC:   {selected.metrics['roc_auc']:.4f}")

    print("\nRegistering selected model...")

    model_version = register_logged_model(
        model_id=str(
            next(
                candidate["model_id"]
                for candidate in candidates
                if candidate["run_id"] == selected.run_id
            )
        )
    )

    print("\nRegistered Model:")
    print(f"Name:    {model_version.name}")
    print(f"Version: {model_version.version}")
    print(f"Status:  {model_version.status}")

    mark_as_candidate(
        model_name=model_version.name,
        model_version=model_version.version,
    )

    print("\nLifecycle status: candidate")
    print("Candidate alias assigned successfully.")


if __name__ == "__main__":
    run_model_selection_pipeline()