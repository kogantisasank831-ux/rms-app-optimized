"""SQLAlchemy model: SkillMaster (LLD 3.2, INV-09 canonical skill vocabulary)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SkillMaster(Base):
    __tablename__ = "skill_master"

    skill_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_name: Mapped[str] = mapped_column(String(120), unique=True)
    skill_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
