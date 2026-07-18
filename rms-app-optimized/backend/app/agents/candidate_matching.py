"""AGENT-3 candidate_matching (LLD 6.4, uses Skill Master — INV-09). Pure function -> validated JSON."""
from __future__ import annotations

import json
import uuid

from app.agents.client import call_claude_json
from app.schemas.matching import CandidateMatchingOutput

SYSTEM = (
    "You are a Candidate Matching engine. Normalize candidate skills to the provided canonical skill "
    "vocabulary (use aliases). Rank candidates for the requisition. Scores must be comparable and "
    "justified by skill coverage and experience."
)

_USER_TMPL = """canonical_skills: {canonical}
min_experience_years: {min_exp}
candidates: {candidates}
Output JSON schema:
{{"ranked": [{{"candidate_id": str, "score": 0-100,
  "matched_essential": [str], "missing_essential": [str], "matched_desired": [str],
  "note": str}}], "method_note": str}}"""


async def run(
    *,
    rrf_id: uuid.UUID,
    canonical_skills: list[dict],
    min_experience_years: float,
    candidates: list[dict],
    triggered_by: uuid.UUID | None = None,
) -> dict:
    user = _USER_TMPL.format(
        canonical=json.dumps(canonical_skills),
        min_exp=min_experience_years,
        candidates=json.dumps(candidates),
    )
    return await call_claude_json(
        agent_name="candidate_matching",
        system=SYSTEM,
        user=user,
        entity_type="RRF",
        entity_id=str(rrf_id),
        schema_model=CandidateMatchingOutput,
        max_tokens=1800,
        triggered_by=triggered_by,
    )
