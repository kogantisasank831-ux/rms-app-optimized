"""candidate_matching agent output schema (LLD 6.4)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RankedCandidate(BaseModel):
    candidate_id: str
    score: float = Field(default=0, ge=0, le=100)
    matched_essential: list[str] = Field(default_factory=list)
    missing_essential: list[str] = Field(default_factory=list)
    matched_desired: list[str] = Field(default_factory=list)
    note: str = ""


class CandidateMatchingOutput(BaseModel):
    ranked: list[RankedCandidate] = Field(default_factory=list)
    method_note: str = ""
