"""Alembic environment.

Uses a SYNC psycopg engine (migrations are simplest synchronous) while the app runtime
uses async asyncpg. The version table and all objects live in the team schema (schema_07);
search_path is pinned so unqualified CREATE TYPE/TABLE land there.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.core.config import settings
from app.db.base import Base  # noqa: F401  (metadata registry for future autogenerate)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
SCHEMA = settings.PG_SCHEMA


def _include_name(name, type_, parent_names):  # keep autogenerate scoped to our schema
    if type_ == "schema":
        return name == SCHEMA
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sync_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # search_path is set at connection time via libpq options (no stray transaction that would
    # prevent alembic from committing under SQLAlchemy 2.0).
    engine = create_engine(
        settings.sync_database_url,
        future=True,
        connect_args={"options": f"-c search_path={SCHEMA},public"},
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=SCHEMA,
            include_schemas=True,
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
