"""SQLAlchemy model: Candidate (LLD 3.2)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base

_SCHEMA = settings.PG_SCHEMA


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_experience_years: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    current_company: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    current_ctc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expected_ctc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(60), server_default=text("'DIRECT'"))
    cv_object_key: Mapped[str] = mapped_column(String(300))
    cv_file_name: Mapped[str] = mapped_column(String(200))
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_cv: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # profile photo renditions (MinIO keys under avatars/); null => fall back to initials
    photo_icon_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_object_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.user_id"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

