from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DatasetRead(BaseModel):
    """Public API representation of a stored dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    row_count: int
    column_count: int
    columns: list[str]
    sha256: str
    status: str
    created_at: datetime


class DatasetPreview(BaseModel):
    """A bounded preview of a dataset."""

    dataset_id: UUID
    name: str
    columns: list[str]
    row_count: int
    preview_rows: list[dict[str, str | None]]
    preview_limit: int = Field(ge=1, le=100)

class DatasetValidationIssue(BaseModel):
    """A data-quality issue discovered during dataset validation."""

    severity: str
    code: str
    message: str
    column: str | None = None


class DatasetColumnProfile(BaseModel):
    """Quality and type statistics for one dataset column."""

    name: str
    inferred_type: str
    missing_count: int
    unique_count: int


class DatasetValidationSummary(BaseModel):
    """Aggregate statistics for a dataset."""

    total_rows: int
    total_columns: int
    missing_cells: int
    duplicate_rows: int


class DatasetValidationReport(BaseModel):
    """Read-only validation and profiling report for a dataset."""

    dataset_id: UUID
    name: str
    is_valid: bool
    summary: DatasetValidationSummary
    columns: list[DatasetColumnProfile]
    issues: list[DatasetValidationIssue]
