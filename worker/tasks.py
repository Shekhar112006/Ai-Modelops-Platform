from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from worker.celery_app import celery_app

from backend.app.db.sync_session import get_session
from backend.app.models.training_job import TrainingJob
from ml.pipeline import run_model_selection_pipeline


@celery_app.task(
    bind=True,
    name="modelops.run_training_job",
)
def run_training_job(
    self,
    job_id: str,
) -> dict[str, object]:
    """Execute a ModelOps training job asynchronously."""

    session = get_session()

    try:
        job = session.get(
            TrainingJob,
            UUID(job_id),
        )

        if job is None:
            raise ValueError(
                f"Training job '{job_id}' was not found."
            )

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()

        result = run_model_selection_pipeline()

        job.status = "succeeded"
        job.selected_model_name = str(
            result["model_name"]
        )
        job.selected_model_version = str(
            result["model_version"]
        )
        job.completed_at = datetime.now(timezone.utc)

        session.commit()

        return result

    except Exception as exc:
        session.rollback()

        job = session.get(
            TrainingJob,
            UUID(job_id),
        )

        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)[
                :4000
            ]
            job.completed_at = datetime.now(
                timezone.utc
            )

            session.commit()

        raise

    finally:
        session.close()