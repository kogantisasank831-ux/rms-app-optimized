"""SQLAlchemy models: Role + User (LLD 3.2). Map to existing schema_07 tables."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base

_SCHEMA = settings.PG_SCHEMA


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    role_code: Mapped[str] = mapped_column(String(30), unique=True)
    role_name: Mapped[str] = mapped_column(String(60))


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(120))
    full_name: Mapped[str] = mapped_column(String(120))
    # FK is schema-qualified because all tables share one MetaData with a default schema.
    role_id: Mapped[int] = mapped_column(ForeignKey(f"{_SCHEMA}.roles.role_id"))
    designation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # profile photo renditions (MinIO keys under avatars/); null => fall back to initials
    photo_icon_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_object_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # eager-load so role is available in async context without lazy IO
    role: Mapped[Role] = relationship(lazy="joined")

    @property
    def role_code(self) -> str:
        return self.role.role_code
