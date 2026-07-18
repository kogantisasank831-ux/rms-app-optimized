"""Interview request/response schemas (Pydantic v2)."""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

Round = Literal["R1_TECH", "R2_TECH", "MANAGEMENT"]
Mode = Literal["VIDEO", "IN_PERSON", "TELEPHONIC"]


class PanelistIn(BaseModel):
    user_id: str
    is_lead: bool = False


class InterviewCreate(BaseModel):
    application_id: str
    round: Round
    scheduled_start: datetime.datetime
    scheduled_end: datetime.datetime
    mode: Mode = "VIDEO"
    meeting_link: str | None = None
    location: str | None = None
    panelists: list[PanelistIn] = Field(default_factory=list)  # INV-05 (1..5) validated in service


class InterviewPatch(BaseModel):
    action: Literal["CANCEL", "NO_SHOW", "RESCHEDULE"]
    comment: str = Field(min_length=1)
    # RESCHEDULE only:
    scheduled_start: datetime.datetime | None = None
    scheduled_end: datetime.datetime | None = None


class PanelistOut(BaseModel):
    user_id: str
    full_name: str
    is_lead: bool


class InterviewOut(BaseModel):
    interview_id: str
    application_id: str
    round: str
    scheduled_start: datetime.datetime
    scheduled_end: datetime.datetime
    mode: str
    meeting_link: str | None
    location: str | None
    status: str
    rescheduled_from: str | None
    panelists: list[PanelistOut]
