"""Async SQLAlchemy engine and session factory.

SQLite for local dev, Postgres for deployment.
DATABASE_URL or BINE_DB_PATH env var controls which is used; defaults to /tmp/bine.db on Vercel and ./bine.db locally.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bine.models import Base

logger = logging.getLogger(__name__)


def resolve_database_url() -> str:
    """Resolve the SQLAlchemy async database URL from environment variables."""
    explicit_url = os.environ.get("DATABASE_URL")
    if explicit_url:
        if explicit_url.startswith("postgresql://"):
            return explicit_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return explicit_url

    db_path = os.environ.get("BINE_DB_PATH")
    if not db_path:
        db_path = "/tmp/bine.db" if os.environ.get("VERCEL") else "./bine.db"
    return f"sqlite+aiosqlite:///{db_path}"


_DATABASE_URL = resolve_database_url()

engine = create_async_engine(
    _DATABASE_URL,
    echo=False,
    # SQLite needs check_same_thread=False for async
    connect_args={"check_same_thread": False} if "sqlite" in _DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables. Safe to call on every startup; never crashes if DB is unwritable."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.warning("init_db failed (continuing without SQLite write access): %s", exc)

