from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionFactory = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
)


def get_session() -> Session:
    """Create a synchronous database session for worker tasks."""

    return SessionFactory()