"""SQLAlchemy models: Interview + InterviewPanelist (LLD 3.2). Native PG enums."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base
from app.models.user import User

_SCHEMA = settings.PG_SCHEMA

interview_round_t = SAEnum(
    "R1_TECH", "R2_TECH", "MANAGEMENT", name="interview_round", schema=_SCHEMA, create_type=False,
)
interview_status_t = SAEnum(
    "SCHEDULED", "COMPLETED", "CANCELLED", "RESCHEDULED", "NO_SHOW",
    name="interview_status", schema=_SCHEMA, create_type=False,
)
interview_mode_t = SAEnum(
    "VIDEO", "IN_PERSON", "TELEPHONIC", name="interview_mode", schema=_SCHEMA, create_type=False,
)


class InterviewPanelist(Base):
    __tablename__ = "interview_panelists"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.interviews.interview_id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.users.user_id"), primary_key=True
    )
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(lazy="joined")


class Interview(Base):
    __tablename__ = "interviews"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.applications.application_id"))
    round: Mapped[str] = mapped_column(interview_round_t)
    scheduled_start: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    mode: Mapped[str] = mapped_column(interview_mode_t, server_default=text("'VIDEO'"))
    meeting_link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(interview_status_t, server_default=text("'SCHEDULED'"))
    rescheduled_from: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{_SCHEMA}.interviews.interview_id"), nullable=True
    )
    scheduling_agent_run: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # cached interview_questions agent output (AGENT-6); null until first generated
    ai_interview_questions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.user_id"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    panelists: Mapped[list[InterviewPanelist]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )

