"""Declarative Base + shared MetaData bound to the team schema (schema_07).

All ORM models inherit from Base so they land in ${PG_SCHEMA}. A consistent naming
convention keeps constraint/index names stable for Alembic.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(schema=settings.PG_SCHEMA, naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = metadata
