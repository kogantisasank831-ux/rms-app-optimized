"""T-206 tests — resume_screening agent (AGENT-1), manual /screen. Live PG + MinIO + Claude."""
from __future__ import annotations

import asyncio
import io
import json
import uuid

import docx
import httpx
import psycopg
from httpx import ASGITransport

from app.core.config import settings
from app.main import create_app

app = create_app()
transport = ASGITransport(app=app)
BASE = "http://test"
HR = {"email": "hr@rms.local", "password": "Passw0rd!23"}
HM = {"email": "hm@rms.local", "password": "Passw0rd!23"}
CV_TEXT = ("Senior engineer with 6 years building AWS solutions in Java. "
           "Hands-on Solace PubSub+, Oracle, microservices and REST APIs.")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _docx(text: str) -> bytes:
    d = docx.Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _bu_id() -> int:
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        return cur.fetchone()[0]


_BU_ID = _bu_id()


async def _setup() -> dict:
    """One APPROVED RRF (with essential skills) + one application to screen."""
    async with _client() as c:
        async def tok(cr):
            r = await c.post("/api/v1/auth/login", json=cr)
            return r.json()["data"]["access_token"]

        hr, hm = await tok(HR), await tok(HM)
        bu_r = await c.post("/api/v1/auth/login", json={"email": "buhead@rms.local", "password": "Passw0rd!23"})
        bu = bu_r.json()["data"]["access_token"]

        skills = (await c.get("/api/v1/skills?limit=3", headers=_h(hr))).json()["data"]
        rid = (await c.post("/api/v1/rrfs", headers=_h(hm), json={
            "position_title": "AWS Java Solace Developer", "positions_count": 2,
            "assignment_location": "Offshore (India)", "justification": "screening test",
            "project_name": "Smart Load", "project_type": "T_AND_M",
            "needed_by_date": "2026-10-01", "min_experience_years": 4, "bu_id": _BU_ID,
            "skills": [{"skill_id": skills[0]["skill_id"], "req_type": "ESSENTIAL", "priority": 5},
                       {"skill_id": skills[1]["skill_id"], "req_type": "DESIRED", "priority": 3}],
        })).json()["data"]["rrf_id"]
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(hm), json={"action": "SUBMIT", "comment": "go"})
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(bu), json={"action": "APPROVE", "comment": "ok"})

        # candidate with rich CV text
        payload = {"full_name": "Gaurav Panchal", "email": f"scr-{uuid.uuid4().hex[:10]}@example.com",
                   "total_experience_years": 6, "source": "PORTAL"}
        files = {"cv_file": ("cv.docx", _docx(CV_TEXT),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        cid = (await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)},
                            files=files, headers=_h(hr))).json()["data"]["candidate_id"]
        aid = (await c.post("/api/v1/applications", headers=_h(hr),
                            json={"rrf_id": rid, "candidate_id": cid})).json()["data"]["application_id"]
        return {"hr": hr, "hm": hm, "aid": aid}


CTX = asyncio.run(_setup())


async def test_manual_screen_persists_and_logs() -> None:
    async with _client() as c:
        r = await c.post(f"/api/v1/applications/{CTX['aid']}/screen", headers=_h(CTX["hr"]))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert 0 <= data["ai_screen_score"] <= 100
        assert data["recommendation"] in ("SHORTLIST", "REVIEW", "REJECT", "")
        assert "result" in data and "match_score" in data["result"]

    # score persisted on the application detail + full result exposed
    async with _client() as c:
        d = await c.get(f"/api/v1/applications/{CTX['aid']}", headers=_h(CTX["hr"]))
        body = d.json()["data"]
        assert body["ai_screen_score"] is not None
        assert body["ai_screen_result"]["match_score"] is not None

    # ai_agent_runs row logged (INV-12)
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as cx, cx.cursor() as cur:
        cur.execute(
            "SELECT status, prompt_tokens, completion_tokens FROM ai_agent_runs "
            "WHERE agent_name='resume_screening' AND entity_id=%s ORDER BY created_at DESC LIMIT 1",
            (CTX["aid"],),
        )
        row = cur.fetchone()
    assert row is not None and row[0] == "SUCCESS" and row[1] > 0 and row[2] > 0


async def test_screen_forbidden_for_hm() -> None:
    async with _client() as c:
        r = await c.post(f"/api/v1/applications/{CTX['aid']}/screen", headers=_h(CTX["hm"]))
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"
