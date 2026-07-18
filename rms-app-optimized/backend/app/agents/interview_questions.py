"""AGENT-6 interview_questions. Pure function -> validated JSON; the service persists.

Suggests interviewer questions tailored to THIS candidate's CV and the role's JD, scoped to
the interview round (R1/R2 technical vs. MANAGEMENT behavioural/leadership) and experience level.
Prior-round focus points are injected by the service (INV-06-safe); the caller never supplies them.
"""
from __future__ import annotations

import json
import uuid

from app.agents.client import call_claude_json
from app.schemas.questions import InterviewQuestionsOutput

_CV_MAX = 12_000  # trim per LLD 6.1 budget rule
_JD_MAX = 4_000

SYSTEM = (
    "You are the Interview Question Generation engine of a Recruitment Management System. "
    "Propose a focused, non-generic set of interview questions the panel can ask THIS candidate "
    "for THIS role and round. Ground every question in concrete evidence from the CV and the job "
    "requirement — probe claimed experience, close gaps against essential skills, and calibrate "
    "difficulty to the candidate's experience level. "
    "Round guidance: R1_TECH / R2_TECH are technical depth rounds (favour technical and "
    "role_specific questions, R2 going deeper than R1); MANAGEMENT is a behavioural/leadership "
    "round (favour behavioural and experience questions — no low-level coding). "
    "For each question give a short rationale (why ask it, tied to the CV/JD) and what a strong "
    "answer looks like. Produce 8-12 questions."
)

_USER_TMPL = """<job>
title: {title} | round: {round} | min_experience_years: {min_exp}
essential_skills: {essential}
desired_skills: {desired}
jd: {jd}
</job>
<candidate>
stated_experience_years: {cand_exp}
cv_text: {cv_text}
</candidate>
prior_round_focus: {prior}
Output JSON schema:
{{"focus_areas": [str],
 "questions": [{{"category": "technical|behavioural|role_specific|experience|process_knowledge",
   "question": str, "rationale": str, "what_to_look_for": str}}],
 "summary": str(<=60 words)}}"""


async def run(
    *,
    interview_id: uuid.UUID,
    round: str,
    position_title: str,
    min_experience_years: float,
    jd_markdown: str,
    essential_skills: list[str],
    desired_skills: list[str],
    cv_text: str,
    candidate_experience_years: float | None,
    prior_round_focus: list[str],
    triggered_by: uuid.UUID | None = None,
) -> dict:
    user = _USER_TMPL.format(
        title=position_title,
        round=round,
        min_exp=min_experience_years,
        essential=", ".join(essential_skills) or "(none listed)",
        desired=", ".join(desired_skills) or "(none listed)",
        jd=(jd_markdown or "")[:_JD_MAX] or "(no JD provided)",
        cand_exp=candidate_experience_years if candidate_experience_years is not None else "unknown",
        cv_text=(cv_text or "")[:_CV_MAX] or "(no CV text extracted)",
        prior=json.dumps(prior_round_focus) if prior_round_focus else "(none)",
    )
    return await call_claude_json(
        agent_name="interview_questions",
        system=SYSTEM,
        user=user,
        entity_type="INTERVIEW",
        entity_id=str(interview_id),
        schema_model=InterviewQuestionsOutput,
        max_tokens=2000,
        triggered_by=triggered_by,
    )
