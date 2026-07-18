"""Application request/response schemas (Pydantic v2)."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    rrf_id: str
    candidate_id: str


class TransitionRequest(BaseModel):
    action: str = Field(min_length=1)
    comment: str = Field(min_length=1)  # INV-01; whitespace-only rejected server-side
    target_stage: str | None = None  # optional ADVANCE target (skip rounds); defaults to next stage


class ApplicationOut(BaseModel):
    application_id: str
    rrf_id: str
    rrf_code: str
    candidate_id: str
    candidate_name: str
    current_stage: str
    status: str
    held_from_stage: str | None
    ai_screen_score: float | None
    created_at: datetime.datetime
