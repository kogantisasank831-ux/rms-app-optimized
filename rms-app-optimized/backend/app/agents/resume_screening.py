"""AGENT-1 resume_screening (LLD 6.2). Pure function -> validated JSON; the service persists."""
from __future__ import annotations

import uuid

from app.agents.client import call_claude_json
from app.schemas.screening import ResumeScreeningResult

_CV_MAX = 12_000  # trim per LLD 6.1 budget rule
_JD_MAX = 4_000

SYSTEM = (
    "You are the Resume Screening engine of a Recruitment Management System. Score a candidate CV "
    "against a job requirement objectively. Penalize missing ESSENTIAL skills heavily; DESIRED skills "
    "add bonus. Judge experience fit against minimum years. Be strict, evidence-based; quote evidence "
    "only from the CV text."
)

_USER_TMPL = """<job>
title: {title} | min_experience_years: {min_exp}
essential_skills: {essential}
desired_skills: {desired}
jd: {jd}
</job>
<candidate>
stated_experience_years: {cand_exp}
cv_text: {cv_text}
</candidate>
Output JSON schema:
{{"match_score": 0-100, "experience_fit": "BELOW|MEETS|EXCEEDS",
 "essential_skill_coverage": [{{"skill": str, "present": bool, "evidence": str}}],
 "missing_essential_skills": [str], "desired_skills_found": [str],
 "strengths": [str, max 5], "risks": [str, max 5],
 "recommendation": "SHORTLIST|REVIEW|REJECT", "rationale": str}}"""


async def run(
    *,
    application_id: uuid.UUID,
    position_title: str,
    min_experience_years: float,
    jd_markdown: str,
    essential_skills: list[str],
    desired_skills: list[str],
    cv_text: str,
    candidate_experience_years: float | None,
    triggered_by: uuid.UUID | None = None,
) -> dict:
    user = _USER_TMPL.format(
        title=position_title,
        min_exp=min_experience_years,
        essential=", ".join(essential_skills) or "(none listed)",
        desired=", ".join(desired_skills) or "(none listed)",
        jd=(jd_markdown or "")[:_JD_MAX] or "(no JD provided)",
        cand_exp=candidate_experience_years if candidate_experience_years is not None else "unknown",
        cv_text=(cv_text or "")[:_CV_MAX] or "(no CV text extracted)",
    )
    return await call_claude_json(
        agent_name="resume_screening",
        system=SYSTEM,
        user=user,
        entity_type="APPLICATION",
        entity_id=str(application_id),
        schema_model=ResumeScreeningResult,
        max_tokens=1500,
        triggered_by=triggered_by,
    )
