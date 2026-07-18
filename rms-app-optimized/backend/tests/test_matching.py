"""T-305 tests — candidate_matching agent (AGENT-3, INV-09 canonical skills). Live PG + Claude."""
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


def _docx(text: str) -> bytes:
    d = docx.Document()
    d.add_paragraph(text)
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def _bu_id() -> int:
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        return cur.fetchone()[0]


BU_ID = _bu_id()


async def _approved_rrf(c, hm, bu, sid) -> str:
    rid = (await c.post("/api/v1/rrfs", headers=_h(hm), json={
        "position_title": "AWS Java Solace Dev", "positions_count": 3,
        "assignment_location": "Offshore (India)", "justification": "match tests",
        "project_name": "Smart Load", "project_type": "T_AND_M",
        "needed_by_date": "2026-10-01", "min_experience_years": 4, "bu_id": BU_ID,
        "skills": [{"skill_id": sid, "req_type": "ESSENTIAL", "priority": 5}],
    })).json()["data"]["rrf_id"]
    await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(hm), json={"action": "SUBMIT", "comment": "go"})
    await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(bu), json={"action": "APPROVE", "comment": "ok"})
    return rid


async def _setup() -> dict:
    async with _client() as c:
        async def tok(cr):
            r = await c.post("/api/v1/auth/login", json=cr)
            return r.json()["data"]["access_token"]

        hr, hm, bu = await tok(HR), await tok(HM), await tok(BUHEAD)
        sid = (await c.get("/api/v1/skills?limit=1", headers=_h(hr))).json()["data"][0]["skill_id"]

        rid1 = await _approved_rrf(c, hm, bu, sid)
        # one candidate + application into the pool
        payload = {"full_name": "Ranked Cand", "email": f"mt-{uuid.uuid4().hex[:10]}@example.com",
                   "total_experience_years": 6, "source": "PORTAL"}
        files = {"cv_file": ("cv.docx", _docx("6 years AWS Java Solace Oracle microservices"),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        cid = (await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)},
                            files=files, headers=_h(hr))).json()["data"]["candidate_id"]
        await c.post("/api/v1/applications", headers=_h(hr), json={"rrf_id": rid1, "candidate_id": cid})

        rid2 = await _approved_rrf(c, hm, bu, sid)  # empty pool
        return {"hr": hr, "bu": bu, "rid1": rid1, "rid2": rid2, "cid": cid}


CTX = asyncio.run(_setup())


async def test_match_ranks_pool() -> None:
    async with _client() as c:
        r = await c.get(f"/api/v1/rrfs/{CTX['rid1']}/match-candidates", headers=_h(CTX["hr"]))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "ranked" in data
        ranked = data["ranked"]
        assert len(ranked) >= 1
        ids = [x["candidate_id"] for x in ranked]
        assert CTX["cid"] in ids
        assert all(0 <= x["score"] <= 100 for x in ranked)


async def test_match_empty_pool() -> None:
    async with _client() as c:
        r = await c.get(f"/api/v1/rrfs/{CTX['rid2']}/match-candidates", headers=_h(CTX["hr"]))
        assert r.status_code == 200
        assert r.json()["data"]["ranked"] == []


async def test_match_forbidden_for_bu_head() -> None:
    async with _client() as c:
        r = await c.get(f"/api/v1/rrfs/{CTX['rid1']}/match-candidates", headers=_h(CTX["bu"]))
        assert r.status_code == 403  # INV-07
        assert r.json()["error"]["code"] == "RMS-E-4031"
