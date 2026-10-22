from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.dataset import Dataset
from backend.app.models.project import Project


class DatasetValidationError(Exception):
    """Raised when an uploaded dataset fails validation."""


class DatasetNotFoundError(Exception):
    """Raised when a requested dataset does not exist."""


class ProjectNotFoundError(Exception):
    """Raised when the requested project does not exist."""


class DatasetService:
    """Business logic for dataset validation and storage."""

    CHUNK_SIZE = 1024 * 1024
    MAX_COLUMNS = 5000

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        max_upload_bytes: int | None = None,
    ) -> None:
        self.storage_dir = Path(
            storage_dir or settings.dataset_storage_dir
        ).resolve()

        self.max_upload_bytes = (
            max_upload_bytes
            if max_upload_bytes is not None
            else settings.dataset_max_upload_bytes
        )

    async def upload_dataset(
        self,
        session: AsyncSession,
        project_id: UUID,
        upload: UploadFile,
        name: str | None = None,
    ) -> Dataset:
        """Validate, store, and register a CSV dataset."""

        project_result = await session.execute(
            select(Project.id).where(Project.id == project_id)
        )
        if project_result.scalar_one_or_none() is None:
            raise ProjectNotFoundError(
                f"Project '{project_id}' was not found."
            )

        original_filename = Path(
            (upload.filename or "").replace("\\", "/")
        ).name

        if (
            not original_filename
            or len(original_filename) > 255
            or Path(original_filename).suffix.lower() != ".csv"
        ):
            raise DatasetValidationError(
                "Upload a CSV file with a valid .csv filename."
            )

        dataset_id = uuid4()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        file_path = self.storage_dir / f"{dataset_id}.csv"
        temporary_path: Path | None = None
        stored_path: Path | None = None

        try:
            size, digest = await self._write_upload(
                upload=upload,
                file_path=file_path,
            )
            stored_path = file_path

            columns, row_count = self._inspect_csv(file_path)

            dataset_name = (
                name.strip()
                if name is not None
                else Path(original_filename).stem
            )

            if not dataset_name or len(dataset_name) > 255:
                raise DatasetValidationError(
                    "Dataset name must contain 1–255 characters."
                )

            dataset = Dataset(
                id=dataset_id,
                project_id=project_id,
                name=dataset_name,
                original_filename=original_filename,
                storage_path=str(file_path),
                content_type="text/csv",
                file_size_bytes=size,
                row_count=row_count,
                column_count=len(columns),
                columns=columns,
                sha256=digest,
                status="ready",
            )

            session.add(dataset)
            await session.flush()
            await session.refresh(dataset)
            await session.commit()

            return dataset

        except Exception:
            await session.rollback()

            if stored_path is not None:
                stored_path.unlink(missing_ok=True)

            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

            raise

        finally:
            await upload.close()

    async def _write_upload(
        self,
        upload: UploadFile,
        file_path: Path,
    ) -> tuple[int, str]:
        """Write an upload in bounded chunks and calculate SHA-256."""

        size = 0
        digest = hashlib.sha256()

        try:
            with file_path.open("xb") as destination:
                while True:
                    chunk = await upload.read(self.CHUNK_SIZE)
                    if not chunk:
                        break

                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise DatasetValidationError(
                            "CSV exceeds the maximum upload size of "
                            f"{self.max_upload_bytes} bytes."
                        )

                    digest.update(chunk)
                    destination.write(chunk)

                destination.flush()
                os.fsync(destination.fileno())

        except Exception:
            file_path.unlink(missing_ok=True)
            raise

        if size == 0:
            file_path.unlink(missing_ok=True)
            raise DatasetValidationError("The uploaded file is empty.")

        return size, digest.hexdigest()

    def _inspect_csv(
        self,
        file_path: Path,
    ) -> tuple[list[str], int]:
        """Validate CSV encoding, headers, and consistent row widths."""

        try:
            with file_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as source:
                reader = csv.reader(source, strict=True)

                try:
                    headers = next(reader)
                except StopIteration as exc:
                    raise DatasetValidationError(
                        "The CSV file has no header row."
                    ) from exc

                if not headers:
                    raise DatasetValidationError(
                        "The CSV file has no columns."
                    )

                if len(headers) > self.MAX_COLUMNS:
                    raise DatasetValidationError(
                        f"CSV files may contain at most "
                        f"{self.MAX_COLUMNS} columns."
                    )

                if any(not header.strip() for header in headers):
                    raise DatasetValidationError(
                        "CSV column names cannot be empty."
                    )

                if len(set(headers)) != len(headers):
                    raise DatasetValidationError(
                        "CSV column names must be unique."
                    )

                row_count = 0

                for row in reader:
                    if len(row) != len(headers):
                        raise DatasetValidationError(
                            f"CSV row {reader.line_num} has "
                            f"{len(row)} fields; expected "
                            f"{len(headers)}."
                        )

                    row_count += 1

                return headers, row_count

        except DatasetValidationError:
            raise
        except (
            UnicodeDecodeError,
            csv.Error,
            OSError,
        ) as exc:
            raise DatasetValidationError(
                "The uploaded file is not a valid UTF-8 CSV."
            ) from exc

    async def list_project_datasets(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> list[Dataset]:
        """List datasets belonging to a project."""

        project_result = await session.execute(
            select(Project.id).where(Project.id == project_id)
        )
        if project_result.scalar_one_or_none() is None:
            raise ProjectNotFoundError(
                f"Project '{project_id}' was not found."
            )

        result = await session.execute(
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.created_at.desc())
        )

        return list(result.scalars().all())

    async def list_datasets(
        self,
        session: AsyncSession,
    ) -> list[Dataset]:
        """List datasets across all projects."""

        result = await session.execute(
            select(Dataset).order_by(Dataset.created_at.desc())
        )

        return list(result.scalars().all())

    async def get_dataset(
        self,
        session: AsyncSession,
        dataset_id: UUID,
    ) -> Dataset:
        """Fetch dataset metadata by ID."""

        result = await session.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )

        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise DatasetNotFoundError(
                f"Dataset '{dataset_id}' was not found."
            )

        return dataset

    async def preview_dataset(
        self,
        session: AsyncSession,
        dataset_id: UUID,
        limit: int | None = None,
    ) -> tuple[Dataset, list[dict[str, str | None]]]:
        """Return a bounded preview of a stored CSV dataset."""

        dataset = await self.get_dataset(session, dataset_id)

        preview_limit = (
            limit
            if limit is not None
            else settings.dataset_preview_max_rows
        )

        if not 1 <= preview_limit <= settings.dataset_preview_max_rows:
            raise DatasetValidationError(
                "Preview limit must be between 1 and "
                f"{settings.dataset_preview_max_rows}."
            )

        file_path = Path(dataset.storage_path).resolve()

        if (
            file_path.parent != self.storage_dir
            or not file_path.is_file()
        ):
            raise DatasetValidationError(
                "The stored dataset file is missing or unavailable."
            )

        rows: list[dict[str, str | None]] = []

        try:
            with file_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as source:
                reader = csv.DictReader(source)

                for row in reader:
                    if len(rows) >= preview_limit:
                        break

                    rows.append(
                        {
                            key: value
                            for key, value in row.items()
                            if key is not None
                        }
                    )

        except (
            UnicodeDecodeError,
            csv.Error,
            OSError,
        ) as exc:
            raise DatasetValidationError(
                "The stored dataset could not be read."
            ) from exc

        return dataset, rows
