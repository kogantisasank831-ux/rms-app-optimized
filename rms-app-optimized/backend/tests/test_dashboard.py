"""T-401/T-402 tests — dashboard metrics + audit/agent-runs viewers. Live PG."""
from __future__ import annotations

import httpx
from httpx import ASGITransport

from app.main import create_app

app = create_app()
transport = ASGITransport(app=app)
BASE = "http://test"
HR = {"email": "hr@rms.local", "password": "Passw0rd!23"}
BUHEAD = {"email": "buhead@rms.local", "password": "Passw0rd!23"}
INTERVIEWER = {"email": "interviewer@rms.local", "password": "Passw0rd!23"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


async def _token(c, creds) -> str:
    r = await c.post("/api/v1/auth/login", json=creds)
    return r.json()["data"]["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def test_metrics_hr_full() -> None:
    async with _client() as c:
        t = await _token(c, HR)
        r = await c.get("/api/v1/dashboard/metrics", headers=_h(t))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        for key in ("open_rrfs", "pending_approvals", "pipeline_by_stage", "offer_acceptance_rate", "agent_usage"):
            assert key in data and "value" in data[key] and "description" in data[key]


async def test_metrics_bu_head_excludes_candidate_data() -> None:
    async with _client() as c:
        t = await _token(c, BUHEAD)
        r = await c.get("/api/v1/dashboard/metrics", headers=_h(t))
        assert r.status_code == 200
        data = r.json()["data"]
        assert "open_rrfs" in data          # RRF-level allowed
        assert "pipeline_by_stage" not in data   # candidate data excluded (INV-07)
        assert "agent_usage" not in data


async def test_audit_viewer_paginated() -> None:
    async with _client() as c:
        t = await _token(c, HR)
        r = await c.get("/api/v1/audit?limit=5", headers=_h(t))
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["limit"] == 5 and "total" in body["meta"]


async def test_agent_runs_viewer() -> None:
    async with _client() as c:
        t = await _token(c, HR)
        r = await c.get("/api/v1/agents/runs?agent_name=resume_screening&limit=5", headers=_h(t))
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)


async def test_audit_forbidden_for_interviewer() -> None:
    async with _client() as c:
        t = await _token(c, INTERVIEWER)
        r = await c.get("/api/v1/audit", headers=_h(t))
        assert r.status_code == 403
