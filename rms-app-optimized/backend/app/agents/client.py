"""Shared Claude wrapper (LLD 6.1).

call_claude_json(): single entry point every agent uses.
  * model=claude-opus-4-8, temperature 0.2, 60s timeout, 2 retries (1s/3s backoff)
  * strips ```json fences, json.loads, one JSON-repair pass on failure
  * optional Pydantic validation (mismatch -> DEGRADED)
  * ALWAYS logs an ai_agent_runs row (INV-12), in its OWN session so the log is durable
    regardless of the caller's transaction
  * on final failure raises AgentFailure (HTTP RMS-E-5021); callers keep a manual path
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.errors import AgentFailure
from app.db.session import SessionLocal

_JSON_ONLY = "Respond with a single valid JSON object only. No prose, no markdown."
_BACKOFF = (1, 3)  # seconds before retry 1 and 2
_MAX_ATTEMPTS = 3  # initial + 2 retries


def strip_fences(raw: str) -> str:
    """Remove markdown code fences around a JSON payload."""
    s = raw.strip()
    if s.startswith("```"):
        s = s[3:]
        if s[:4].lower() == "json":
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def parse_json(raw: str) -> dict:
    return json.loads(strip_fences(raw))


async def _log_run(**fields: Any) -> None:
    """Insert one ai_agent_runs row in an independent session (INV-12)."""
    async with SessionLocal() as db:
        await db.execute(
            text(
                "INSERT INTO ai_agent_runs "
                "(agent_name, entity_type, entity_id, model, input_digest, output, "
                " prompt_tokens, completion_tokens, latency_ms, status, error_detail, triggered_by) "
                "VALUES (:an,:et,:eid,:model, CAST(:idg AS jsonb), CAST(:out AS jsonb), "
                " :pt,:ct,:lat,:st,:err,:tb)"
            ),
            fields,
        )
        await db.commit()


async def call_claude_json(
    *,
    agent_name: str,
    system: str,
    user: str,
    entity_type: str,
    entity_id: str,
    schema_model: type | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    triggered_by: uuid.UUID | None = None,
) -> dict:
    import anthropic

    client = anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=float(settings.AGENT_TIMEOUT_S),
    )
    full_system = system.rstrip() + "\n\n" + _JSON_ONLY

    # NOTE: claude-opus-4-8 deprecates `temperature` (400 if sent). The param is kept in the
    # signature for interface stability but is intentionally NOT passed to the API. (ADR-006)
    _ = temperature

    # only transient failures are worth retrying; 4xx (e.g. BadRequest) fail fast
    retryable = (
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        anthropic.RateLimitError,
        anthropic.InternalServerError,
    )

    started = time.perf_counter()
    prompt_tokens = completion_tokens = 0
    last_error: str | None = None

    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                system=full_system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens,
            )
            prompt_tokens += resp.usage.input_tokens
            completion_tokens += resp.usage.output_tokens
            raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

            try:
                data = parse_json(raw)
            except json.JSONDecodeError:
                # one repair pass
                repair = await client.messages.create(
                    model=settings.CLAUDE_MODEL,
                    system=_JSON_ONLY,
                    messages=[{"role": "user", "content": f"Return ONLY valid JSON for:\n{raw}"}],
                    max_tokens=max_tokens,
                )
                prompt_tokens += repair.usage.input_tokens
                completion_tokens += repair.usage.output_tokens
                repaired = "".join(b.text for b in repair.content if getattr(b, "type", "") == "text")
                data = parse_json(repaired)

            status = "SUCCESS"
            if schema_model is not None:
                try:
                    data = schema_model(**data).model_dump()
                except Exception as exc:  # noqa: BLE001 — pydantic ValidationError etc.
                    status = "DEGRADED"
                    last_error = f"schema validation failed: {exc}"

            latency_ms = int((time.perf_counter() - started) * 1000)
            await _log_run(
                an=agent_name, et=entity_type, eid=entity_id, model=settings.CLAUDE_MODEL,
                idg=json.dumps({"system_len": len(full_system), "user_len": len(user)}),
                out=json.dumps(data), pt=prompt_tokens, ct=completion_tokens, lat=latency_ms,
                st=status, err=last_error, tb=str(triggered_by) if triggered_by else None,
            )
            if status == "DEGRADED":
                raise AgentFailure(f"Agent {agent_name} returned invalid schema", code="RMS-E-5021")
            return data

        except AgentFailure:
            raise
        except retryable as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(_BACKOFF[attempt])
                continue
            break
        except json.JSONDecodeError as exc:
            # repair also failed to yield JSON — retry a fresh generation
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(_BACKOFF[attempt])
                continue
            break
        except anthropic.APIError as exc:
            # non-retryable (4xx etc.) — fail fast
            last_error = f"{type(exc).__name__}: {exc}"
            break

    # all attempts exhausted -> log FAILURE, raise
    latency_ms = int((time.perf_counter() - started) * 1000)
    await _log_run(
        an=agent_name, et=entity_type, eid=entity_id, model=settings.CLAUDE_MODEL,
        idg=json.dumps({"system_len": len(full_system), "user_len": len(user)}),
        out=None, pt=prompt_tokens, ct=completion_tokens, lat=latency_ms,
        st="FAILURE", err=last_error, tb=str(triggered_by) if triggered_by else None,
    )
    raise AgentFailure(f"Agent {agent_name} failed after {_MAX_ATTEMPTS} attempts: {last_error}",
                       code="RMS-E-5021")
