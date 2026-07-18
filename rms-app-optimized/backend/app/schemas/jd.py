"""JD version request/response schemas (Pydantic v2) — T-203."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class JdManualSave(BaseModel):
    """HM/HR edit saved as a new (non-agent) version — INV: editable before submit."""

    jd_markdown: str = Field(min_length=1)


class JdVersionOut(BaseModel):
    jd_id: str
    version_no: int
    jd_markdown: str
    generated_by_agent: bool
    created_by: str
    created_at: datetime.datetime


class JdGenerateResult(BaseModel):
    version: JdVersionOut
    seo_title: str = ""
    keywords: list[str] = Field(default_factory=list)
