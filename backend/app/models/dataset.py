from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class Dataset(Base):
    """Metadata for a CSV dataset associated with an ML project."""

    __tablename__ = "datasets"

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_datasets_file_size_positive",
        ),
        CheckConstraint(
            "row_count >= 0",
            name="ck_datasets_row_count_nonnegative",
        ),
        CheckConstraint(
            "column_count > 0",
            name="ck_datasets_column_count_positive",
        ),
        CheckConstraint(
            "status IN ('uploaded', 'ready', 'failed')",
            name="ck_datasets_status",
        ),
        Index(
            "ix_datasets_project_created",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="text/csv",
        server_default="text/csv",
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    row_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    columns: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ready",
        server_default="ready",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
