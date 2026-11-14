"""
Async SQLAlchemy engine and session factory.

Usage:
    from backend.app.db.session import get_db, engine

    async with get_db() as session:
        result = await session.execute(select(Variable))
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.config import settings

logger = logging.getLogger("backend.db.session")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# Create the async engine once at module import time.
# pool_pre_ping=True detects stale connections before use.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory (expire_on_commit=False avoids lazy-load after commit)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autobegin=True,
)


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager that provides a session and commits on success, rolls back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
