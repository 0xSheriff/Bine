"""Async SQLAlchemy engine and session factory.

SQLite for local dev, Postgres for deployment.
DATABASE_URL env var controls which is used; defaults to SQLite at ./bine.db.
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bine.models import Base

_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./bine.db")

# Postgres driver needs asyncpg, not psycopg2
if _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

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
    """Create all tables. Safe to call on every startup — only creates if missing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
