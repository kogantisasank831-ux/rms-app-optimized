"""AGENT-4 interview_scheduling (LLD 6.5). Pure function -> validated JSON.

Agent output is ADVISORY; the service does a deterministic non-overlap re-check before use.
"""
from __future__ import annotations

import json
import uuid

from app.agents.client import call_claude_json
from app.schemas.scheduling import SchedulingOutput

SYSTEM = (
    "You are an Interview Scheduling engine. Propose conflict-free slots maximizing panelist overlap "
    "inside working hours and candidate windows. Never propose a slot overlapping any busy interval."
)

_USER_TMPL = """timezone: Asia/Kolkata ; working_hours: 09:00-18:00 ; duration_minutes: {duration} ; round: {round}
candidate_windows: {windows}
panelists: {panelists}
Output JSON schema:
{{"proposals": [{{"start": iso8601, "end": iso8601, "available_panelists": [user_id],
  "conflicts": [str], "rank": int, "reason": str}}], "no_slot_found": bool}}"""


async def run(
    *,
    application_id: uuid.UUID,
    round: str,
    candidate_windows: list[dict],
    panelists: list[dict],
    duration_minutes: int = 60,
    triggered_by: uuid.UUID | None = None,
) -> dict:
    user = _USER_TMPL.format(
        duration=duration_minutes,
        round=round,
        windows=json.dumps(candidate_windows),
        panelists=json.dumps(panelists),
    )
    return await call_claude_json(
        agent_name="interview_scheduling",
        system=SYSTEM,
        user=user,
        entity_type="APPLICATION",
        entity_id=str(application_id),
        schema_model=SchedulingOutput,
        max_tokens=1500,
        triggered_by=triggered_by,
    )
