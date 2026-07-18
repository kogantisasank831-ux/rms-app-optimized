"""Interview feedback request/response schemas (Pydantic v2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Recommendation = Literal["SELECT", "REJECT", "HOLD"]


class SkillRatingIn(BaseModel):
    skill_id: int
    rating: int = Field(ge=1, le=5)
    remarks: str | None = None


# Canonical assessment categories captured on every consolidated feedback.
# Technical rounds (R1/R2) require behavioural + technical (process_knowledge optional);
# the Management round is behavioural-only. Enforced per-round in interview_service.
AssessmentCategory = Literal["behavioural", "technical", "process_knowledge"]
REQUIRED_ASSESSMENT_CATEGORIES: tuple[str, ...] = ("behavioural", "technical")


class CategoryAssessmentIn(BaseModel):
    category: AssessmentCategory
    rating: int | None = Field(default=None, ge=1, le=5)
    comments: str | None = None


class FeedbackCreate(BaseModel):
    overall_rating: float = Field(ge=1, le=5)
    recommendation: Recommendation
    strengths: str | None = None
    weaknesses: str | None = None
    raw_notes: str | None = None
    attributes: dict = Field(default_factory=dict)
    assessments: list[CategoryAssessmentIn] = Field(default_factory=list)
    skill_ratings: list[SkillRatingIn] = Field(default_factory=list)


class SkillRatingOut(BaseModel):
    skill_id: int
    skill_name: str
    rating: int
    remarks: str | None


class CategoryAssessmentOut(BaseModel):
    category: str
    rating: int | None = None
    comments: str | None = None


class FeedbackOut(BaseModel):
    feedback_id: str
    interview_id: str
    overall_rating: float
    recommendation: str
    strengths: str | None
    weaknesses: str | None
    raw_notes: str | None
    attributes: dict
    assessments: list[CategoryAssessmentOut] = Field(default_factory=list)
    ai_summary: dict | None
    skill_ratings: list[SkillRatingOut]
    interview_status: str


class PriorFeedbackItem(BaseModel):
    round: str
    overall_rating: float
    recommendation: str
    strengths: str | None
    weaknesses: str | None
    assessments: list[CategoryAssessmentOut] = Field(default_factory=list)
    ai_summary: dict | None


class PerSkillAssessment(BaseModel):
    skill: str
    assessment: str = ""


class FeedbackSummaryOutput(BaseModel):
    """feedback_summarization agent output (LLD 6.6)."""
    executive_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    per_skill: list[PerSkillAssessment] = Field(default_factory=list)
    consistency_with_prior_rounds: str = ""
    suggested_focus_next_round: list[str] = Field(default_factory=list)
    final_recommendation_echo: str = ""
