"""Add persistent training result metrics.

Revision ID: a31d35d3b9f9
Revises: 1661ee77d1d1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a31d35d3b9f9"
down_revision: Union[str, Sequence[str], None] = "1661ee77d1d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add result fields to existing training jobs."""

    op.add_column(
        "training_jobs",
        sa.Column(
            "metrics",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "training_jobs",
        sa.Column(
            "quality_gate_passed",
            sa.Boolean(),
            nullable=True,
        ),
    )

    op.add_column(
        "training_jobs",
        sa.Column(
            "selected_candidate",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "training_jobs",
        sa.Column(
            "selected_model_id",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the added result fields."""

    op.drop_column("training_jobs", "selected_model_id")
    op.drop_column("training_jobs", "selected_candidate")
    op.drop_column("training_jobs", "quality_gate_passed")
    op.drop_column("training_jobs", "metrics")
