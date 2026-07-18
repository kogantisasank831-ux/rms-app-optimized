"""interview_questions agent output schema. Used to validate the model's JSON."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SuggestedQuestion(BaseModel):
    # category kept as plain str for robustness against minor model drift
    category: str = ""            # technical | behavioural | role_specific | experience | process_knowledge
    question: str
    rationale: str = ""           # why this question, given the CV + JD
    what_to_look_for: str = ""    # signals of a strong answer


class InterviewQuestionsOutput(BaseModel):
    focus_areas: list[str] = Field(default_factory=list)
    questions: list[SuggestedQuestion] = Field(default_factory=list)
    summary: str = ""
