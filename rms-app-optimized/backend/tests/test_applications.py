"""T-205 tests — Applications + pipeline transitions (G6-G14) + INV-01/02/03. Live PG + MinIO.

Module setup creates ONE APPROVED RRF and caches tokens; each test then creates a fresh
candidate + application so the (rrf, candidate) dedupe guard doesn't collide.
"""
from __future__ import annotations

import asyncio
import io
import json
import uuid

import docx
import httpx
from httpx import ASGITransport

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
    d.add_paragraph("AWS Java Solace Oracle microservices experience")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


async def _setup() -> dict:
    async with _client() as c:
        async def tok(cr):
            r = await c.post("/api/v1/auth/login", json=cr)
            return r.json()["data"]["access_token"]

        hr, hm, bu = await tok(HR), await tok(HM), await tok(BUHEAD)
        sid = (await c.get("/api/v1/skills?limit=1", headers=_h(hr))).json()["data"][0]["skill_id"]
        r = await c.post("/api/v1/rrfs", headers=_h(hm), json={
            "position_title": "Pipeline Test Role", "positions_count": 5,
            "assignment_location": "Offshore (India)", "justification": "pipeline tests",
            "project_name": "Smart Load", "project_type": "T_AND_M",
            "needed_by_date": "2026-10-01", "min_experience_years": 3, "bu_id": _BU_ID,
            "skills": [{"skill_id": sid, "req_type": "ESSENTIAL", "priority": 5}],
        })
        rid = r.json()["data"]["rrf_id"]
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(hm),
                     json={"action": "SUBMIT", "comment": "review"})
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(bu),
                     json={"action": "APPROVE", "comment": "approved"})
        return {"hr": hr, "hm": hm, "bu": bu, "rid": rid}


def _get_bu_id() -> int:
    import psycopg
    from app.core.config import settings
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        return cur.fetchone()[0]


_BU_ID = _get_bu_id()
CTX = asyncio.run(_setup())


async def _new_candidate(c, token) -> str:
    payload = {"full_name": "Pipeline Cand", "email": f"pc-{uuid.uuid4().hex[:10]}@example.com",
               "source": "PORTAL"}
    files = {"cv_file": ("cv.docx", _docx(),
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)}, files=files, headers=_h(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]["candidate_id"]


async def _new_application(c, token) -> dict:
    cid = await _new_candidate(c, CTX["hr"])
    r = await c.post("/api/v1/applications", headers=_h(token),
                     json={"rrf_id": CTX["rid"], "candidate_id": cid})
    assert r.status_code == 201, r.text
    return {**r.json()["data"], "candidate_id": cid}


async def _tr(c, token, aid, action, comment="ok"):
    return await c.post(f"/api/v1/applications/{aid}/transition",
                        json={"action": action, "comment": comment}, headers=_h(token))


async def test_create_g6_autoscreen_and_dupguard() -> None:
    async with _client() as c:
        cid = await _new_candidate(c, CTX["hr"])
        r = await c.post("/api/v1/applications", headers=_h(CTX["hr"]),
                         json={"rrf_id": CTX["rid"], "candidate_id": cid})
        assert r.status_code == 201, r.text
        assert r.json()["data"]["current_stage"] == "SCREENING"  # G6 auto-advance (cv_text present)
        # duplicate (rrf, candidate) -> 409
        r2 = await c.post("/api/v1/applications", headers=_h(CTX["hr"]),
                          json={"rrf_id": CTX["rid"], "candidate_id": cid})
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "RMS-E-4091"


async def test_advance_screening_to_shortlisted() -> None:
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        r = await _tr(c, CTX["hr"], app_["application_id"], "ADVANCE", "looks strong")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["current_stage"] == "SHORTLISTED"


async def test_advance_to_r1_blocked_without_interview() -> None:
    """G8 guard: cannot enter INTERVIEW_R1 without a scheduled R1 interview."""
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        aid = app_["application_id"]
        await _tr(c, CTX["hr"], aid, "ADVANCE", "shortlist")  # -> SHORTLISTED
        r = await _tr(c, CTX["hr"], aid, "ADVANCE", "to interview")  # -> needs R1 interview
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4221"


async def test_reject_sets_status() -> None:
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        r = await _tr(c, CTX["hr"], app_["application_id"], "REJECT", "not a fit")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "REJECTED"


async def test_hold_resume_roundtrip() -> None:
    """G14 / INV-03: hold from a stage, resume returns to held_from_stage."""
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        aid = app_["application_id"]
        await _tr(c, CTX["hr"], aid, "ADVANCE", "shortlist")  # SHORTLISTED
        r = await _tr(c, CTX["hr"], aid, "HOLD", "pause")
        assert r.json()["data"]["status"] == "ON_HOLD"
        r = await _tr(c, CTX["hr"], aid, "RESUME", "back on")
        body = r.json()["data"]
        assert body["status"] == "ACTIVE" and body["current_stage"] == "SHORTLISTED"


async def test_comment_required_whitespace() -> None:
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        r = await _tr(c, CTX["hr"], app_["application_id"], "ADVANCE", "   ")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4222"


async def test_hm_can_advance_own_rrf() -> None:
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        r = await _tr(c, CTX["hm"], app_["application_id"], "ADVANCE", "hm advances own")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["current_stage"] == "SHORTLISTED"


async def test_bu_head_cannot_transition() -> None:
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        r = await _tr(c, CTX["bu"], app_["application_id"], "ADVANCE", "bu tries")
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_hm_cannot_create_application() -> None:
    async with _client() as c:
        cid = await _new_candidate(c, CTX["hr"])
        r = await c.post("/api/v1/applications", headers=_h(CTX["hm"]),
                         json={"rrf_id": CTX["rid"], "candidate_id": cid})
        assert r.status_code == 403


async def test_history_records_transitions() -> None:
    async with _client() as c:
        app_ = await _new_application(c, CTX["hr"])
        aid = app_["application_id"]
        await _tr(c, CTX["hr"], aid, "ADVANCE", "shortlist")
        r = await c.get(f"/api/v1/applications/{aid}/history", headers=_h(CTX["hr"]))
        assert r.status_code == 200
        actions = [h["action"] for h in r.json()["data"]]
        # auto-screen (create) + advance
        assert actions.count("ADVANCE") >= 2
