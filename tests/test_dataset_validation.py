from __future__ import annotations

import csv
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient

from backend.app.db.session import get_session
from backend.app.main import app
import pytest

from backend.app.api.datasets import dataset_service


from backend.app.models.dataset import Dataset
from backend.app.services.dataset_service import DatasetService


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write test rows to a temporary CSV file."""
    if not rows:
        raise ValueError("Test CSV must contain at least one row.")

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class FakeResult:
    """Simulate the result returned by a database query."""

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset

    def scalar_one_or_none(self) -> Dataset:
        return self.dataset


class FakeSession:
    """Provide a minimal async session for service-level tests."""

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset

    async def execute(self, statement) -> FakeResult:
        return FakeResult(self.dataset)

@pytest.mark.asyncio
async def test_profile_clean_dataset(tmp_path: Path) -> None:
    """A clean numeric dataset has no missing or duplicate rows."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"feature_01": "10", "feature_02": "20", "target": "30"},
            {"feature_01": "15", "feature_02": "25", "target": "40"},
            {"feature_01": "20", "feature_02": "30", "target": "50"},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Clean test dataset",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=3,
        column_count=3,
        columns=["feature_01", "feature_02", "target"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    assert report.is_valid is True
    assert report.summary.total_rows == 3
    assert report.summary.total_columns == 3
    assert report.summary.missing_cells == 0
    assert report.summary.duplicate_rows == 0
    assert report.issues == []

    assert all(
        column.inferred_type == "integer"
        for column in report.columns
    )
    assert all(column.unique_count == 3 for column in report.columns)


@pytest.mark.asyncio
async def test_profile_missing_values(tmp_path: Path) -> None:
    """Empty cells are counted globally and per column."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"age": "20", "score": "80"},
            {"age": "", "score": "90"},
            {"age": "30", "score": ""},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Missing values test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=3,
        column_count=2,
        columns=["age", "score"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    assert report.summary.total_rows == 3
    assert report.summary.missing_cells == 2
    assert report.summary.duplicate_rows == 0

    profiles = {column.name: column for column in report.columns}

    assert profiles["age"].missing_count == 1
    assert profiles["score"].missing_count == 1
    assert any(
        issue.code == "missing_values"
        for issue in report.issues
    )


@pytest.mark.asyncio
async def test_profile_duplicate_rows(tmp_path: Path) -> None:
    """Repeated records are counted beyond their first occurrence."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"age": "20", "score": "80"},
            {"age": "25", "score": "90"},
            {"age": "20", "score": "80"},
            {"age": "20", "score": "80"},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Duplicate rows test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=4,
        column_count=2,
        columns=["age", "score"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    assert report.summary.total_rows == 4
    assert report.summary.duplicate_rows == 2
    assert any(
        issue.code == "duplicate_rows"
        for issue in report.issues
    )



@pytest.mark.asyncio
async def test_profile_mixed_data_types(tmp_path: Path) -> None:
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(file_path, [
        {"age": "20", "price": "12.5", "date": "2026-01-15", "name": "Alice"},
        {"age": "30", "price": "18.75", "date": "2026-02-20", "name": "Bob"},
    ])

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Mixed types test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=2,
        column_count=4,
        columns=["age", "price", "date", "name"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    profiles = {column.name: column for column in report.columns}

    assert profiles["age"].inferred_type == "integer"
    assert profiles["price"].inferred_type == "float"
    assert profiles["date"].inferred_type == "date"
    assert profiles["name"].inferred_type == "string"


@pytest.mark.asyncio
async def test_profile_entirely_empty_column(tmp_path: Path) -> None:
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(file_path, [
        {"name": "Alice", "optional_field": ""},
        {"name": "Bob", "optional_field": ""},
    ])

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Empty column test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=2,
        column_count=2,
        columns=["name", "optional_field"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    profiles = {column.name: column for column in report.columns}

    assert profiles["optional_field"].inferred_type == "unknown"
    assert profiles["optional_field"].missing_count == 2
    assert report.summary.missing_cells == 2
    assert any(
        issue.code == "unknown_type"
        and issue.column == "optional_field"
        for issue in report.issues
    )


@pytest.mark.asyncio
async def test_profile_missing_dataset_file(tmp_path: Path) -> None:
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    # Intentionally do not create the CSV file.
    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Missing file test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=0,
        row_count=0,
        column_count=0,
        columns=[],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)

    with pytest.raises(Exception, match="stored dataset file is missing or unavailable"):
        await service.validate_dataset(
            session=FakeSession(dataset),
            dataset_id=dataset_id,
        )




def test_validate_dataset_api_returns_report(tmp_path: Path) -> None:
    """The API returns a profiling report for an existing dataset."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(file_path, [
        {"age": "20", "score": "80"},
        {"age": "30", "score": "90"},
    ])

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="API validation test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=2,
        column_count=2,
        columns=["age", "score"],
        sha256="test",
        status="ready",
    )

    original_storage_dir = dataset_service.storage_dir
    dataset_service.storage_dir = tmp_path.resolve()

    class Result:
        def scalar_one_or_none(self) -> Dataset:
            return dataset

    class Session:
        async def execute(self, statement) -> Result:
            return Result()

    async def override_session():
        yield Session()

    previous = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = override_session

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/datasets/{dataset_id}/validate"
            )
    finally:
        dataset_service.storage_dir = original_storage_dir

        if previous is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous
    print("API error details:", response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_id"] == str(dataset_id)
    assert data["summary"]["total_rows"] == 2
    assert data["summary"]["total_columns"] == 2
    assert data["summary"]["missing_cells"] == 0


def test_validate_unknown_dataset_api_returns_404() -> None:
    """The API returns 404 when the dataset does not exist."""
    missing_id = uuid4()

    class Result:
        def scalar_one_or_none(self) -> None:
            return None

    class Session:
        async def execute(self, statement) -> Result:
            return Result()

    async def override_session():
        yield Session()

    previous = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = override_session

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/datasets/{missing_id}/validate"
            )
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_validate_missing_file_api_returns_400(tmp_path: Path) -> None:
    """The API returns 400 when the stored CSV file is unavailable."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Missing file API test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=0,
        row_count=0,
        column_count=0,
        columns=[],
        sha256="test",
        status="ready",
    )

    class Result:
        def scalar_one_or_none(self) -> Dataset:
            return dataset

    class Session:
        async def execute(self, statement) -> Result:
            return Result()

    async def override_session():
        yield Session()

    previous = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = override_session

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/datasets/{dataset_id}/validate"
            )
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous

    assert response.status_code == 400
    assert "stored dataset file is missing" in response.json()["detail"]


@pytest.mark.asyncio
async def test_profile_common_missing_markers(tmp_path: Path) -> None:
    """Common missing-value markers are counted as missing cells."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"name": "Alice", "score": "10"},
            {"name": "NA", "score": "N/A"},
            {"name": "null", "score": "None"},
            {"name": "NaN", "score": "20"},
            {"name": "Bob", "score": "30"},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Missing markers test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=5,
        column_count=2,
        columns=["name", "score"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    profiles = {column.name: column for column in report.columns}

    assert report.summary.missing_cells == 5
    assert profiles["name"].missing_count == 3
    assert profiles["score"].missing_count == 2
    assert profiles["name"].unique_count == 2
    assert profiles["score"].unique_count == 3


@pytest.mark.asyncio
async def test_profile_whitespace_and_valid_zero_values(
    tmp_path: Path,
) -> None:
    """Whitespace is missing, but zero and false remain valid values."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"quantity": "0", "enabled": "False"},
            {"quantity": "   ", "enabled": "True"},
            {"quantity": "5", "enabled": "  "},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Whitespace and valid values test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=3,
        column_count=2,
        columns=["quantity", "enabled"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    profiles = {column.name: column for column in report.columns}

    assert report.summary.missing_cells == 2
    assert profiles["quantity"].missing_count == 1
    assert profiles["enabled"].missing_count == 1
    assert profiles["quantity"].inferred_type == "integer"
    assert profiles["enabled"].inferred_type == "boolean"
    assert profiles["quantity"].unique_count == 2
    assert profiles["enabled"].unique_count == 2


@pytest.mark.asyncio
async def test_duplicate_detection_normalizes_missing_markers(
    tmp_path: Path,
) -> None:
    """Rows with equivalent missing markers count as duplicates."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"age": "NA", "score": "90"},
            {"age": "N/A", "score": "90"},
            {"age": "25", "score": "80"},
        ],
    )

    original_content = file_path.read_text(encoding="utf-8")

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Normalized duplicates test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=3,
        column_count=2,
        columns=["age", "score"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    assert report.summary.duplicate_rows == 1
    assert any(
        issue.code == "duplicate_rows"
        for issue in report.issues
    )
    assert file_path.read_text(encoding="utf-8") == original_content


@pytest.mark.asyncio
async def test_profile_reports_inconsistent_numeric_values(
    tmp_path: Path,
) -> None:
    """Report non-numeric values in a mostly numeric column."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"age": "20"},
            {"age": "30"},
            {"age": "unknown"},
            {"age": "40"},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Inconsistent numeric values test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=4,
        column_count=1,
        columns=["age"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    assert any(
        issue.code == "inconsistent_values"
        and issue.column == "age"
        for issue in report.issues
    )

@pytest.mark.asyncio
async def test_profile_does_not_flag_mixed_categorical_values(
    tmp_path: Path,
) -> None:
    """Mixed categorical values should not trigger numeric warnings."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"status": "active"},
            {"status": "1"},
            {"status": "pending"},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Mixed categorical values test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=3,
        column_count=1,
        columns=["status"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    assert not any(
        issue.code == "inconsistent_values"
        and issue.column == "status"
        for issue in report.issues
    )


@pytest.mark.asyncio
async def test_profile_still_detects_invalid_value_in_numeric_column(
    tmp_path: Path,
) -> None:
    """A mostly numeric column should still report invalid values."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"price": "10.5"},
            {"price": "20.0"},
            {"price": "invalid"},
            {"price": "30.5"},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Invalid numeric value test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=4,
        column_count=1,
        columns=["price"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)
    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    issue = next(
        (
            issue
            for issue in report.issues
            if issue.code == "inconsistent_values"
            and issue.column == "price"
        ),
        None,
    )

    assert issue is not None
    assert "1 non-numeric value(s)" in issue.message
    assert "'invalid'" in issue.message

@pytest.mark.asyncio
async def test_duplicate_detection_does_not_confuse_literal_missing_marker(
    tmp_path: Path,
) -> None:
    """A literal '<MISSING>' value must not collide with missing cells."""
    dataset_id = uuid4()
    file_path = tmp_path / f"{dataset_id}.csv"

    write_csv(
        file_path,
        [
            {"name": "<MISSING>", "score": "90"},
            {"name": "", "score": "90"},
        ],
    )

    dataset = Dataset(
        id=dataset_id,
        project_id=uuid4(),
        name="Missing marker collision test",
        original_filename=file_path.name,
        storage_path=str(file_path),
        content_type="text/csv",
        file_size_bytes=file_path.stat().st_size,
        row_count=2,
        column_count=2,
        columns=["name", "score"],
        sha256="test",
        status="ready",
    )

    service = DatasetService(storage_dir=tmp_path)

    report = await service.validate_dataset(
        session=FakeSession(dataset),
        dataset_id=dataset_id,
    )

    assert report.summary.duplicate_rows == 0