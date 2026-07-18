"""Candidate request/response schemas (Pydantic v2)."""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["DIRECT", "REFERRAL", "PORTAL", "IJP"]


class CandidateCreate(BaseModel):
    """JSON `payload` part of the multipart request (the CV file is a separate part)."""
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    phone: str | None = None
    total_experience_years: float | None = Field(default=None, ge=0)
    current_company: str | None = None
    notice_period_days: int | None = Field(default=None, ge=0)
    current_ctc: str | None = None
    expected_ctc: str | None = None
    source: Source = "DIRECT"


class CandidateListItem(BaseModel):
    candidate_id: str
    full_name: str
    email: str
    source: str
    total_experience_years: float | None
    current_company: str | None
    cv_file_name: str
    created_at: datetime.datetime


class CandidateOut(CandidateListItem):
    phone: str | None
    notice_period_days: int | None
    current_ctc: str | None
    expected_ctc: str | None
    cv_object_key: str
    cv_download_url: str | None
    cv_text: str | None
    parsed_cv: dict | None
    created_by: str
