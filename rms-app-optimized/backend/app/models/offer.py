"""SQLAlchemy model: Offer (LLD 3.2). Native PG enum offer_status."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base

_SCHEMA = settings.PG_SCHEMA

offer_status_t = SAEnum(
    "DRAFT", "RELEASED", "ACCEPTED", "DECLINED", "WITHDRAWN", "EXPIRED",
    name="offer_status", schema=_SCHEMA, create_type=False,
)


class Offer(Base):
    __tablename__ = "offers"

    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.applications.application_id"), unique=True
    )
    offer_code: Mapped[str] = mapped_column(String(24), unique=True)
    designation: Mapped[str] = mapped_column(String(120))
    ctc_annual: Mapped[str] = mapped_column(String(60))            # Total Cost to Company
    monthly_gross: Mapped[str | None] = mapped_column(String(60), nullable=True)
    joining_date: Mapped[datetime.date] = mapped_column(Date)
    work_location: Mapped[str] = mapped_column(String(120))        # base / joining location
    candidate_name: Mapped[str | None] = mapped_column(String(120), nullable=True)  # optional override
    letter_object_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(offer_status_t, server_default=text("'DRAFT'"))
    valid_until: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    generated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.user_id"))
    released_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

