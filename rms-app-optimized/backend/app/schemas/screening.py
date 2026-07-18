"""resume_screening agent output schema (LLD 6.2). Used to validate the model's JSON."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EssentialCoverage(BaseModel):
    skill: str
    present: bool = False
    evidence: str = ""


class ResumeScreeningResult(BaseModel):
    # enum-ish fields kept as plain str for robustness against minor model drift
    match_score: float = Field(ge=0, le=100)
    experience_fit: str = ""            # BELOW | MEETS | EXCEEDS
    essential_skill_coverage: list[EssentialCoverage] = Field(default_factory=list)
    missing_essential_skills: list[str] = Field(default_factory=list)
    desired_skills_found: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendation: str = ""            # SHORTLIST | REVIEW | REJECT
    rationale: str = ""
