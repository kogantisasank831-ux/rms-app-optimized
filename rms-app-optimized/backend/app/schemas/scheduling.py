"""interview_scheduling agent I/O schemas (LLD 6.5)."""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

Round = Literal["R1_TECH", "R2_TECH", "MANAGEMENT"]


class Window(BaseModel):
    start: datetime.datetime
    end: datetime.datetime


class SuggestSlotsRequest(BaseModel):
    application_id: str
    round: Round
    candidate_windows: list[Window] = Field(default_factory=list)
    panelist_ids: list[str] = Field(default_factory=list)


class SchedulingProposal(BaseModel):
    start: str
    end: str
    available_panelists: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    rank: int = 0
    reason: str = ""


class SchedulingOutput(BaseModel):
    proposals: list[SchedulingProposal] = Field(default_factory=list)
    no_slot_found: bool = False
