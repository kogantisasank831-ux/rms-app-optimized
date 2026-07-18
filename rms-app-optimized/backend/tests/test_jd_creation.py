"""T-203 tests — jd_creation agent (AGENT-2) + JD version management. Runs against live PG.

One test issues a real (small) Claude call to prove AGENT-2 is live and logs ai_agent_runs
(INV-12); the rest exercise versioning + RBAC with no model calls.
"""
from __future__ import annotations

import httpx
import psycopg
from httpx import ASGITransport

from app.core.config import settings
from app.main import create_app

app = create_app()
transport = ASGITransport(app=app)
BASE = "http://test"
HM = {"email": "hm@rms.local", "password": "Passw0rd!23"}
HR = {"email": "hr@rms.local", "password": "Passw0rd!23"}
BUHEAD = {"email": "buhead@rms.local", "password": "Passw0rd!23"}
INTERVIEWER = {"email": "interviewer@rms.local", "password": "Passw0rd!23"}


def _bu_id() -> int:
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        return cur.fetchone()[0]


BU_ID = _bu_id()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


async def _token(c: httpx.AsyncClient, creds: dict) -> str:
    r = await c.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _skill_ids(c: httpx.AsyncClient, token: str, n: int = 2) -> list[int]:
    r = await c.get("/api/v1/skills?limit=10", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    return [s["skill_id"] for s in r.json()["data"][:n]]


async def _create_rrf(c: httpx.AsyncClient, token: str) -> str:
    ids = await _skill_ids(c, token)
    payload = {
        "position_title": "AWS + Java + Solace Developer",
        "positions_count": 2,
        "assignment_location": "Offshore (India)",
        "base_location": "Kolkata",
        "justification": "SmartLoad TIBCO migration - billable",
        "project_name": "Smart Load",
        "project_type": "T_AND_M",
        "needed_by_date": "2026-08-01",
        "min_experience_years": 4,
        "wfh_allowed": True,
        "bu_id": BU_ID,
        "skills": [
            {"skill_id": ids[0], "req_type": "ESSENTIAL", "priority": 5},
            {"skill_id": ids[1], "req_type": "DESIRED", "priority": 3},
        ],
    }
    r = await c.post("/api/v1/rrfs", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return r.json()["data"]["rrf_id"]


async def test_generate_jd_creates_version_and_logs_run() -> None:
    """Live AGENT-2 call: produces v1 (agent-authored) and an ai_agent_runs row (INV-12)."""
    async with _client() as c:
        token = await _token(c, HM)
        rrf_id = await _create_rrf(c, token)
        r = await c.post(
            f"/api/v1/rrfs/{rrf_id}/jd/generate", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        version = data["version"]
        assert version["version_no"] == 1
        assert version["generated_by_agent"] is True
        assert version["jd_markdown"].strip(), "empty JD markdown"

        # listed and readable back
        lst = await c.get(f"/api/v1/rrfs/{rrf_id}/jd", headers={"Authorization": f"Bearer {token}"})
        assert lst.status_code == 200, lst.text
        assert any(v["jd_id"] == version["jd_id"] for v in lst.json()["data"])

    # INV-12: an ai_agent_runs row was written for this RRF by the jd_creation agent
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status, model FROM ai_agent_runs "
            "WHERE agent_name='jd_creation' AND entity_id=%s ORDER BY created_at DESC LIMIT 1",
            (rrf_id,),
        )
        row = cur.fetchone()
    assert row is not None, "no ai_agent_runs row logged for jd_creation"
    assert row[0] == "SUCCESS", f"agent status {row[0]}"
    assert row[1] == "claude-opus-4-8"


async def test_manual_save_versions_increment() -> None:
    """Hand-edited saves create successive non-agent versions; history is newest-first."""
    async with _client() as c:
        token = await _token(c, HM)
        rrf_id = await _create_rrf(c, token)

        r1 = await c.post(
            f"/api/v1/rrfs/{rrf_id}/jd",
            json={"jd_markdown": "# Draft JD v1\nHand-written."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["data"]["version_no"] == 1
        assert r1.json()["data"]["generated_by_agent"] is False

        r2 = await c.post(
            f"/api/v1/rrfs/{rrf_id}/jd",
            json={"jd_markdown": "# Draft JD v2\nRevised."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["data"]["version_no"] == 2

        lst = await c.get(f"/api/v1/rrfs/{rrf_id}/jd", headers={"Authorization": f"Bearer {token}"})
        vnos = [v["version_no"] for v in lst.json()["data"]]
        assert vnos == [2, 1], vnos


async def test_manual_save_rejects_empty() -> None:
    async with _client() as c:
        token = await _token(c, HM)
        rrf_id = await _create_rrf(c, token)
        r = await c.post(
            f"/api/v1/rrfs/{rrf_id}/jd",
            json={"jd_markdown": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"


async def test_bu_head_cannot_write_but_can_read() -> None:
    """INV-07-adjacent: BU_HEAD is read-only on JDs of their BU; cannot generate or edit."""
    async with _client() as c:
        hm = await _token(c, HM)
        rrf_id = await _create_rrf(c, hm)  # created in BU_ID = BU head's unit

        bu = await _token(c, BUHEAD)
        gen = await c.post(
            f"/api/v1/rrfs/{rrf_id}/jd/generate", headers={"Authorization": f"Bearer {bu}"}
        )
        assert gen.status_code == 403
        assert gen.json()["error"]["code"] == "RMS-E-4031"

        save = await c.post(
            f"/api/v1/rrfs/{rrf_id}/jd",
            json={"jd_markdown": "sneaky"},
            headers={"Authorization": f"Bearer {bu}"},
        )
        assert save.status_code == 403

        read = await c.get(f"/api/v1/rrfs/{rrf_id}/jd", headers={"Authorization": f"Bearer {bu}"})
        assert read.status_code == 200, read.text


async def test_interviewer_cannot_read_jd() -> None:
    async with _client() as c:
        hm = await _token(c, HM)
        rrf_id = await _create_rrf(c, hm)
        iv = await _token(c, INTERVIEWER)
        r = await c.get(f"/api/v1/rrfs/{rrf_id}/jd", headers={"Authorization": f"Bearer {iv}"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"
