"""SQLAlchemy models: RRF + RrfSkill (LLD 3.2). Native PG enums (create_type=False)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base
from app.models.business_unit import BusinessUnit
from app.models.skill import SkillMaster

_SCHEMA = settings.PG_SCHEMA

# reference existing PG enum types (do not re-create)
rrf_status_t = SAEnum(
    "DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "ON_HOLD",
    "CANCEL_REQUESTED", "CANCELLED", "CLOSED",
    name="rrf_status", schema=_SCHEMA, create_type=False,
)
project_type_t = SAEnum(
    "T_AND_M", "FIXED_FEE", name="project_type", schema=_SCHEMA, create_type=False,
)
skill_req_type_t = SAEnum(
    "ESSENTIAL", "DESIRED", name="skill_req_type", schema=_SCHEMA, create_type=False,
)


class RrfSkill(Base):
    __tablename__ = "rrf_skills"

    rrf_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.rrf.rrf_id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey(f"{_SCHEMA}.skill_master.skill_id"), primary_key=True
    )
    req_type: Mapped[str] = mapped_column(skill_req_type_t)
    priority: Mapped[int] = mapped_column(SmallInteger, default=3)

    skill: Mapped[SkillMaster] = relationship(lazy="joined")


class RRF(Base):
    __tablename__ = "rrf"

    rrf_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    rrf_code: Mapped[str] = mapped_column(String(20), unique=True)  # internal requisition id
    job_code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)  # public job id (careers portal)
    position_title: Mapped[str] = mapped_column(String(120))
    positions_count: Mapped[int] = mapped_column(SmallInteger)
    assignment_location: Mapped[str] = mapped_column(String(80))
    base_location: Mapped[str | None] = mapped_column(String(80), nullable=True)
    justification: Mapped[str] = mapped_column(Text)
    project_name: Mapped[str] = mapped_column(String(120))
    project_type: Mapped[str] = mapped_column(project_type_t)
    needed_by_date: Mapped[datetime.date] = mapped_column(Date)
    salary_range: Mapped[str | None] = mapped_column(String(60), nullable=True)
    wfh_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    shift_hours: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reporting_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scope_of_work: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    education_qualification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    min_experience_years: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    bu_id: Mapped[int] = mapped_column(ForeignKey(f"{_SCHEMA}.business_units.bu_id"))
    status: Mapped[str] = mapped_column(rrf_status_t, server_default=text("'DRAFT'"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.user_id"))
    hr_rep_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{_SCHEMA}.users.user_id"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{_SCHEMA}.users.user_id"), nullable=True
    )
    approved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    held_from_status: Mapped[str | None] = mapped_column(rrf_status_t, nullable=True)
    positions_filled: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    skills: Mapped[list[RrfSkill]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )
    business_unit: Mapped[BusinessUnit] = relationship(lazy="joined")

