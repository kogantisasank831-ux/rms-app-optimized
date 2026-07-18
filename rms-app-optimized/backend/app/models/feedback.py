"""SQLAlchemy models: InterviewFeedback + InterviewSkillRating (LLD 3.2).

INV-04: exactly one consolidated feedback per interview (UNIQUE interview_id).
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base
from app.models.skill import SkillMaster

_SCHEMA = settings.PG_SCHEMA

recommendation_t = SAEnum(
    "SELECT", "REJECT", "HOLD", name="recommendation", schema=_SCHEMA, create_type=False,
)


class InterviewSkillRating(Base):
    __tablename__ = "interview_skill_ratings"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.interview_feedback.feedback_id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey(f"{_SCHEMA}.skill_master.skill_id"), primary_key=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger)
    remarks: Mapped[str | None] = mapped_column(String(300), nullable=True)

    skill: Mapped[SkillMaster] = relationship(lazy="joined")


class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.interviews.interview_id"), unique=True  # INV-04
    )
    overall_rating: Mapped[float] = mapped_column(Numeric(3, 1))
    recommendation: Mapped[str] = mapped_column(recommendation_t)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'"))
    ai_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.user_id"))
    submitted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    skill_ratings: Mapped[list[InterviewSkillRating]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )
