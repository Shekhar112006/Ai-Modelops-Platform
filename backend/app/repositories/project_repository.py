from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.project import Project


class ProjectRepository:
    """Database operations for projects."""

    async def create(
        self,
        session: AsyncSession,
        project: Project,
    ) -> Project:
        """Persist a project and return the refreshed entity."""

        session.add(project)

        await session.flush()
        await session.refresh(project)

        return project

    async def list(
        self,
        session: AsyncSession,
    ) -> list[Project]:
        """Return projects ordered by creation time."""

        result = await session.execute(
            select(Project).order_by(
                Project.created_at.desc()
            )
        )

        return list(result.scalars().all())