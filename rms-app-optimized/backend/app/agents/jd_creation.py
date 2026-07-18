"""AI agent: jd_creation — AGENT-2 (LLD 6.3).

Pure function: turns requisition facts into a job description. Builds the prompt, calls the
shared Claude wrapper with a Pydantic output contract, returns validated JSON. The service
(jd_service) persists the result as a new rrf_jd_versions row. Never invents facts beyond the
requisition; the wrapper always logs an ai_agent_runs row (INV-12).
"""
from __future__ import annotations

import json
import uuid

from pydantic import BaseModel, Field

from app.agents.client import call_claude_json

_SYSTEM = (
    "You are a senior technical recruiter writing precise, unbiased job descriptions for "
    "enterprise IT roles. Use only the provided requisition facts; never invent benefits, "
    "salary, or company claims. Output professional markdown INSIDE the JSON string field. "
    "Respond with a single valid JSON object only. No prose outside JSON."
)


class JdCreationOutput(BaseModel):
    """Contract for the agent's JSON (LLD 6.3). Mismatch => DEGRADED in call_claude_json."""

    jd_markdown: str = Field(min_length=1)
    seo_title: str = ""
    keywords: list[str] = Field(default_factory=list)


def _skill_line(skills: list[dict], req_type: str) -> str:
    names = [s["skill_name"] for s in skills if s.get("req_type") == req_type]
    return ", ".join(names) if names else "(none specified)"


def build_user_prompt(rrf: dict, skills: list[dict]) -> str:
    """USER template per LLD 6.3. Only JD-relevant facts are sent (no internal ids/audit)."""
    facts = {
        "position_title": rrf["position_title"],
        "positions_count": rrf["positions_count"],
        "assignment_location": rrf["assignment_location"],
        "base_location": rrf.get("base_location"),
        "project_name": rrf["project_name"],
        "project_type": rrf["project_type"],
        "min_experience_years": rrf["min_experience_years"],
        "education_qualification": rrf.get("education_qualification"),
        "wfh_allowed": rrf["wfh_allowed"],
        "shift_hours": rrf.get("shift_hours"),
        "reporting_to": rrf.get("reporting_to"),
        "scope_of_work": rrf.get("scope_of_work"),
        "responsibilities": rrf.get("responsibilities"),
    }
    return (
        f"requisition: {json.dumps(facts, default=str)}\n"
        f"essential_skills: {_skill_line(skills, 'ESSENTIAL')} ; "
        f"desired_skills: {_skill_line(skills, 'DESIRED')}\n"
        "Sections required in jd_markdown: Role Summary, Key Responsibilities, Essential Skills, "
        "Desired Skills, Qualifications & Experience, Engagement Details "
        "(location/WFH/shift/project type).\n"
        'Output JSON schema: {"jd_markdown": str, "seo_title": str, "keywords": [str]}'
    )


async def generate_jd(
    rrf: dict,
    skills: list[dict],
    *,
    rrf_id: str,
    triggered_by: uuid.UUID | None = None,
) -> dict:
    """Return validated {jd_markdown, seo_title, keywords}. Raises AgentFailure on failure."""
    return await call_claude_json(
        agent_name="jd_creation",
        system=_SYSTEM,
        user=build_user_prompt(rrf, skills),
        entity_type="RRF",
        entity_id=rrf_id,
        schema_model=JdCreationOutput,
        max_tokens=2000,
        triggered_by=triggered_by,
    )
