from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.project import Project
from backend.app.repositories.project_repository import (
    ProjectRepository,
)


class ProjectAlreadyExistsError(Exception):
    """Raised when a project name is already registered."""


class ProjectService:
    """Business logic for project management."""

    def __init__(
        self,
        repository: ProjectRepository | None = None,
    ) -> None:
        self.repository = repository or ProjectRepository()

    async def create_project(
        self,
        session: AsyncSession,
        name: str,
        description: str | None,
    ) -> Project:
        """Create a project while enforcing domain-level uniqueness."""

        project = Project(
            name=name,
            description=description,
        )

        try:
            project = await self.repository.create(
                session,
                project,
            )
            await session.commit()

        except IntegrityError as exc:
            await session.rollback()
            raise ProjectAlreadyExistsError(
                f"Project '{name}' already exists."
            ) from exc

        return project

    async def list_projects(
        self,
        session: AsyncSession,
    ) -> list[Project]:
        """Return all projects."""

        return await self.repository.list(session)