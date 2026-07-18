"""Async engine + sessionmaker. search_path is pinned to the team schema on every connection."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# asyncpg passes server settings via connect_args; this pins search_path=schema_07,public
_engine_kwargs: dict = {
    "echo": False,
    "pool_pre_ping": True,  # validate a connection before use (server may have dropped idle ones)
    "connect_args": {"server_settings": {"search_path": f"{settings.PG_SCHEMA},public"}},
}
if settings.APP_ENV == "test":
    # NullPool: fresh connection per use, never reused across event loops (avoids test hangs)
    _engine_kwargs["poolclass"] = NullPool
else:
    # The DB is a SHARED, centrally-provided Postgres (many teams -> low max_connections budget).
    # Keep this process's footprint small: <=10 connections total (5 pooled + 5 overflow), recycle
    # every 30 min so long-lived connections don't get reaped server-side and go stale.
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 5
    _engine_kwargs["pool_recycle"] = 1800
    _engine_kwargs["pool_timeout"] = 30

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a session (see core/deps.py)."""
    async with SessionLocal() as session:
        yield session
