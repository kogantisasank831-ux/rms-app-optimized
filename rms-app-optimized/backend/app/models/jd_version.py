"""SQLAlchemy model: RrfJdVersion (LLD 3.2 `rrf_jd_versions`).

One row per JD version of an RRF. version_no is monotonic per rrf (UNIQUE rrf_id, version_no);
generated_by_agent distinguishes AGENT-2 output from a manual HM edit. Append-only in practice
(a new edit is a new version, never an in-place mutation).
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base

_SCHEMA = settings.PG_SCHEMA


class RrfJdVersion(Base):
    __tablename__ = "rrf_jd_versions"

    jd_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    rrf_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.rrf.rrf_id", ondelete="CASCADE")
    )
    version_no: Mapped[int] = mapped_column(SmallInteger)
    jd_markdown: Mapped[str] = mapped_column(Text)
    generated_by_agent: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.user_id"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
