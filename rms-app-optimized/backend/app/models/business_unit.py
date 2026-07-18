"""SQLAlchemy model: BusinessUnit (LLD 3.2)."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base

_SCHEMA = settings.PG_SCHEMA


class BusinessUnit(Base):
    __tablename__ = "business_units"

    bu_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bu_name: Mapped[str] = mapped_column(String(100), unique=True)
    bu_head_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.user_id"))
