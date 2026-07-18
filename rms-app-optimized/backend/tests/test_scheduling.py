"""T-302 tests — interview_scheduling agent (AGENT-4) + deterministic non-overlap re-check. Live."""
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
INTERVIEWER = {"email": "interviewer@rms.local", "password": "Passw0rd!23"}


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


def _fixtures() -> tuple[int, str]:
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as c, c.cursor() as cur:
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

        hr, hm, bu, ivt = await tok(HR), await tok(HM), await tok(BUHEAD), await tok(INTERVIEWER)
        sid = (await c.get("/api/v1/skills?limit=1", headers=_h(hr))).json()["data"][0]["skill_id"]
        rid = (await c.post("/api/v1/rrfs", headers=_h(hm), json={
            "position_title": "Sched Test", "positions_count": 2,
            "assignment_location": "Offshore (India)", "justification": "sched tests",
            "project_name": "Smart Load", "project_type": "T_AND_M",
            "needed_by_date": "2026-10-01", "min_experience_years": 3, "bu_id": BU_ID,
            "skills": [{"skill_id": sid, "req_type": "ESSENTIAL", "priority": 5}],
        })).json()["data"]["rrf_id"]
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(hm), json={"action": "SUBMIT", "comment": "go"})
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(bu), json={"action": "APPROVE", "comment": "ok"})
        payload = {"full_name": "Sched Cand", "email": f"sc-{uuid.uuid4().hex[:10]}@example.com", "source": "PORTAL"}
        files = {"cv_file": ("cv.docx", _docx(),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        cid = (await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)},
                            files=files, headers=_h(hr))).json()["data"]["candidate_id"]
        aid = (await c.post("/api/v1/applications", headers=_h(hr),
                            json={"rrf_id": rid, "candidate_id": cid})).json()["data"]["application_id"]
        return {"hr": hr, "iv": ivt, "aid": aid}


CTX = asyncio.run(_setup())


async def test_suggest_slots_returns_verified_proposals() -> None:
    async with _client() as c:
        body = {
            "application_id": CTX["aid"], "round": "R1_TECH",
            "candidate_windows": [{"start": "2026-08-03T09:00:00Z", "end": "2026-08-03T13:00:00Z"}],
            "panelist_ids": [IV_UID],
        }
        r = await c.post("/api/v1/interviews/suggest-slots", json=body, headers=_h(CTX["hr"]))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "proposals" in data and "no_slot_found" in data
        # deterministic re-check annotated every proposal
        for p in data["proposals"]:
            assert "verified" in p


async def test_suggest_slots_forbidden_for_interviewer() -> None:
    async with _client() as c:
        body = {"application_id": CTX["aid"], "round": "R1_TECH",
                "candidate_windows": [{"start": "2026-08-03T09:00:00Z", "end": "2026-08-03T13:00:00Z"}],
                "panelist_ids": [IV_UID]}
        r = await c.post("/api/v1/interviews/suggest-slots", json=body, headers=_h(CTX["iv"]))
        assert r.status_code == 403
