from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.schemas.activity import ActivityRead
from backend.app.services.activity_service import ActivityService


router = APIRouter()

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]

activity_service = ActivityService()


@router.get(
    "",
    response_model=list[ActivityRead],
)
async def get_recent_activities(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[ActivityRead]:
    """Return recent activities across the platform."""

    return await activity_service.get_recent_activities(
        session=session,
        limit=limit,
    )
