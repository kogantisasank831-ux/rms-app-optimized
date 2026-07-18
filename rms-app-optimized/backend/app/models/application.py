"""SQLAlchemy model: Application (LLD 3.2). Native PG enums (create_type=False)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base
from app.models.candidate import Candidate
from app.models.rrf import RRF

_SCHEMA = settings.PG_SCHEMA

app_stage_t = SAEnum(
    "APPLIED", "SCREENING", "SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2",
    "INTERVIEW_MGMT", "OFFER", "OFFER_ACCEPTED", "JOINED",
    name="app_stage", schema=_SCHEMA, create_type=False,
)
app_status_t = SAEnum(
    "ACTIVE", "ON_HOLD", "REJECTED", "WITHDRAWN", "HIRED",
    name="app_status", schema=_SCHEMA, create_type=False,
)
stage_action_t = SAEnum(
    "ADVANCE", "REJECT", "HOLD", "RESUME", "WITHDRAW",
    name="stage_action", schema=_SCHEMA, create_type=False,
)


class Application(Base):
    __tablename__ = "applications"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    rrf_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.rrf.rrf_id"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.candidates.candidate_id"))
    current_stage: Mapped[str] = mapped_column(app_stage_t, server_default=text("'APPLIED'"))
    status: Mapped[str] = mapped_column(app_status_t, server_default=text("'ACTIVE'"))
    held_from_stage: Mapped[str | None] = mapped_column(app_stage_t, nullable=True)
    ai_screen_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ai_screen_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    rrf: Mapped[RRF] = relationship(lazy="joined")
    candidate: Mapped[Candidate] = relationship(lazy="joined")

