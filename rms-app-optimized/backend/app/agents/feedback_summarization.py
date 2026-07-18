"""AGENT-5 feedback_summarization (LLD 6.6). Pure function -> validated JSON; service persists.

Prior-round summaries are injected by the service (INV-06-safe); the caller never supplies them.
"""
from __future__ import annotations

import json
import uuid

from app.agents.client import call_claude_json
from app.schemas.feedback import FeedbackSummaryOutput

SYSTEM = (
    "You are an Interview Feedback Summarization engine. Produce a neutral, evidence-based "
    "consolidated summary for hiring decisions. Do not soften negatives or exaggerate positives. "
    "The 'attributes.assessments' array carries per-dimension ratings/comments "
    "(behavioural, technical, and optionally process_knowledge) — weigh each dimension explicitly "
    "in the executive summary, strengths, and concerns."
)

_USER_TMPL = """round: {round} ; overall_rating: {rating} ; recommendation: {rec}
skill_ratings: {skill_ratings}
attributes: {attributes} ; raw_panel_notes: {raw_notes}
prior_round_summaries: {prior}
Output JSON schema:
{{"executive_summary": str(<=80 words), "strengths": [str], "concerns": [str],
 "per_skill": [{{"skill": str, "assessment": str}}],
 "consistency_with_prior_rounds": str, "suggested_focus_next_round": [str],
 "final_recommendation_echo": "SELECT|REJECT|HOLD"}}"""


async def run(
    *,
    interview_id: uuid.UUID,
    round: str,
    overall_rating: float,
    recommendation: str,
    skill_ratings: list[dict],
    attributes: dict,
    raw_notes: str | None,
    prior_round_summaries: list[dict],
    triggered_by: uuid.UUID | None = None,
) -> dict:
    user = _USER_TMPL.format(
        round=round,
        rating=overall_rating,
        rec=recommendation,
        skill_ratings=json.dumps(skill_ratings),
        attributes=json.dumps(attributes or {}),
        raw_notes=(raw_notes or "(none)")[:6000],
        prior=json.dumps(prior_round_summaries),
    )
    return await call_claude_json(
        agent_name="feedback_summarization",
        system=SYSTEM,
        user=user,
        entity_type="INTERVIEW",
        entity_id=str(interview_id),
        schema_model=FeedbackSummaryOutput,
        max_tokens=1200,
        triggered_by=triggered_by,
    )
