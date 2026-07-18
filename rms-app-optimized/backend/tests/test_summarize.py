"""T-304 tests — feedback_summarization agent (AGENT-5). Live PG + Claude."""
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
BUHEAD = {"email": "buhead@rms.local", "password": "Passw0rd!23"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _docx() -> bytes:
    d = docx.Document()
    d.add_paragraph("Engineer")
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def _db():
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    return psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public")


def _fixtures() -> tuple[int, str]:
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        bu = cur.fetchone()[0]
        cur.execute("SELECT user_id FROM users WHERE lower(email)='interviewer@rms.local'")
        iv = str(cur.fetchone()[0])
    return bu, iv


BU_ID, IV_UID = _fixtures()


async def _setup() -> dict:
    async with _client() as c:
        async def tok(cr):
            r = await c.post("/api/v1/auth/login", json=cr)
            return r.json()["data"]["access_token"]

        hr, hm, bu = await tok(HR), await tok(HM), await tok(BUHEAD)
        sid = (await c.get("/api/v1/skills?limit=1", headers=_h(hr))).json()["data"][0]["skill_id"]
        rid = (await c.post("/api/v1/rrfs", headers=_h(hm), json={
            "position_title": "Summarize Test", "positions_count": 2,
            "assignment_location": "Offshore (India)", "justification": "sum tests",
            "project_name": "Smart Load", "project_type": "T_AND_M",
            "needed_by_date": "2026-10-01", "min_experience_years": 3, "bu_id": BU_ID,
            "skills": [{"skill_id": sid, "req_type": "ESSENTIAL", "priority": 5}],
        })).json()["data"]["rrf_id"]
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(hm), json={"action": "SUBMIT", "comment": "go"})
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(bu), json={"action": "APPROVE", "comment": "ok"})

        payload = {"full_name": "Sum Cand", "email": f"sum-{uuid.uuid4().hex[:10]}@example.com", "source": "PORTAL"}
        files = {"cv_file": ("cv.docx", _docx(),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        cid = (await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)},
                            files=files, headers=_h(hr))).json()["data"]["candidate_id"]
        aid = (await c.post("/api/v1/applications", headers=_h(hr),
                            json={"rrf_id": rid, "candidate_id": cid})).json()["data"]["application_id"]
        await c.post(f"/api/v1/applications/{aid}/transition", headers=_h(hr),
                     json={"action": "ADVANCE", "comment": "shortlist"})
        iid = (await c.post("/api/v1/interviews", headers=_h(hr), json={
            "application_id": aid, "round": "R1_TECH", "scheduled_start": "2026-08-01T09:30:00Z",
            "scheduled_end": "2026-08-01T10:30:00Z", "mode": "VIDEO",
            "panelists": [{"user_id": IV_UID, "is_lead": True}]})).json()["data"]["interview_id"]
        await c.post(f"/api/v1/interviews/{iid}/feedback", headers=_h(hr), json={
            "overall_rating": 4.0, "recommendation": "SELECT",
            "strengths": "Strong AWS and Solace event patterns", "weaknesses": "Limited Step Functions",
            "raw_notes": "Panelist notes: solid hands-on cloud, good communication.",
            "skill_ratings": [{"skill_id": sid, "rating": 4, "remarks": "hands-on"}]})
        return {"hr": hr, "iid": iid}


CTX = asyncio.run(_setup())


async def test_summarize_persists_ai_summary() -> None:
    async with _client() as c:
        r = await c.post(f"/api/v1/interviews/{CTX['iid']}/feedback/summarize", headers=_h(CTX["hr"]))
        assert r.status_code == 200, r.text
        summary = r.json()["data"]["ai_summary"]
        assert "executive_summary" in summary
        assert "final_recommendation_echo" in summary

    # ai_agent_runs row logged (INV-12)
    with _db() as cx, cx.cursor() as cur:
        cur.execute(
            "SELECT status FROM ai_agent_runs WHERE agent_name='feedback_summarization' "
            "AND entity_id=%s ORDER BY created_at DESC LIMIT 1",
            (CTX["iid"],),
        )
        row = cur.fetchone()
    assert row is not None and row[0] == "SUCCESS"
