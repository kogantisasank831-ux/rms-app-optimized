"""T-107 tests — Claude wrapper. Offline parser checks + one live call proving ai_agent_runs logging."""
from __future__ import annotations

import psycopg

from app.agents.client import call_claude_json, parse_json, strip_fences
from app.core.config import settings


# ---- offline (no API) ----
def test_strip_fences_plain() -> None:
    assert strip_fences('{"a":1}') == '{"a":1}'


def test_strip_fences_json_block() -> None:
    assert strip_fences("```json\n{\"a\":1}\n```") == '{"a":1}'


def test_parse_json_fenced() -> None:
    assert parse_json("```\n{\"ping\":\"pong\"}\n```") == {"ping": "pong"}


# ---- live (uses the provided Claude key; minimal tokens) ----
async def test_live_call_logs_agent_run() -> None:
    result = await call_claude_json(
        agent_name="_t107_probe",
        system="You are a test fixture.",
        user='Return this exact JSON object: {"ping": "pong", "n": 42}',
        entity_type="TEST",
        entity_id="t107",
        max_tokens=100,
    )
    assert isinstance(result, dict)
    assert result.get("ping") == "pong"

    # verify an ai_agent_runs row was written (INV-12)
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as c, c.cursor() as cur:
        cur.execute(
            "SELECT status, prompt_tokens, completion_tokens, model "
            "FROM ai_agent_runs WHERE agent_name='_t107_probe' ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None, "no ai_agent_runs row logged"
    status, pt, ct, model = row
    assert status == "SUCCESS"
    assert pt > 0 and ct > 0
    assert model == "claude-opus-4-8"
