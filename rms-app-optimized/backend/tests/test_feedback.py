"""T-303 tests — consolidated feedback (INV-04, G15) + prior-feedback (INV-06). Live PG.

Chains the real flow: shortlist -> schedule R1 -> advance to INTERVIEW_R1 -> submit R1 feedback
-> advance to INTERVIEW_R2 -> schedule R2 -> read prior-feedback (must show R1).
"""
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
    d.add_paragraph("Experienced engineer")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _db():
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    return psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public")


def _fixtures() -> tuple[int, str, str]:
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        bu = cur.fetchone()[0]
        cur.execute("SELECT user_id FROM users WHERE lower(email)='interviewer@rms.local'")
        iv = str(cur.fetchone()[0])
        cur.execute("SELECT user_id FROM users WHERE lower(email)='hr@rms.local'")
        hr = str(cur.fetchone()[0])
    return bu, iv, hr


BU_ID, IV_UID, HR_UID = _fixtures()


async def _setup() -> dict:
    async with _client() as c:
        async def tok(cr):
            r = await c.post("/api/v1/auth/login", json=cr)
            return r.json()["data"]["access_token"]

        hr, hm, bu, ivt = await tok(HR), await tok(HM), await tok(BUHEAD), await tok(INTERVIEWER)
        sid = (await c.get("/api/v1/skills?limit=1", headers=_h(hr))).json()["data"][0]["skill_id"]
        rid = (await c.post("/api/v1/rrfs", headers=_h(hm), json={
            "position_title": "Feedback Test Role", "positions_count": 3,
            "assignment_location": "Offshore (India)", "justification": "fb tests",
            "project_name": "Smart Load", "project_type": "T_AND_M",
            "needed_by_date": "2026-10-01", "min_experience_years": 3, "bu_id": BU_ID,
            "skills": [{"skill_id": sid, "req_type": "ESSENTIAL", "priority": 5}],
        })).json()["data"]["rrf_id"]
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(hm), json={"action": "SUBMIT", "comment": "go"})
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(bu), json={"action": "APPROVE", "comment": "ok"})
        return {"hr": hr, "hm": hm, "iv": ivt, "rid": rid, "sid": sid}


CTX = asyncio.run(_setup())


async def _shortlisted_app(c) -> str:
    payload = {"full_name": "FB Cand", "email": f"fb-{uuid.uuid4().hex[:10]}@example.com", "source": "PORTAL"}
    files = {"cv_file": ("cv.docx", _docx(),
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    cid = (await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)},
                        files=files, headers=_h(CTX["hr"]))).json()["data"]["candidate_id"]
    aid = (await c.post("/api/v1/applications", headers=_h(CTX["hr"]),
                        json={"rrf_id": CTX["rid"], "candidate_id": cid})).json()["data"]["application_id"]
    await c.post(f"/api/v1/applications/{aid}/transition", headers=_h(CTX["hr"]),
                 json={"action": "ADVANCE", "comment": "shortlist"})
    return aid


async def _schedule(c, aid, rnd, lead=IV_UID) -> str:
    body = {"application_id": aid, "round": rnd, "scheduled_start": "2026-08-01T09:30:00Z",
            "scheduled_end": "2026-08-01T10:30:00Z", "mode": "VIDEO",
            "panelists": [{"user_id": lead, "is_lead": True}]}
    r = await c.post("/api/v1/interviews", json=body, headers=_h(CTX["hr"]))
    assert r.status_code == 201, r.text
    return r.json()["data"]["interview_id"]


def _fb_body(sid: int, rating=4.0, rec="SELECT") -> dict:
    return {"overall_rating": rating, "recommendation": rec, "strengths": "strong on AWS",
            "skill_ratings": [{"skill_id": sid, "rating": 4, "remarks": "hands-on"}]}


async def test_submit_feedback_g15() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        iid = await _schedule(c, aid, "R1_TECH")
        r = await c.post(f"/api/v1/interviews/{iid}/feedback", json=_fb_body(CTX["sid"]), headers=_h(CTX["hr"]))
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["interview_status"] == "COMPLETED"  # G15
        assert len(data["skill_ratings"]) == 1


async def test_duplicate_feedback_conflict() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        iid = await _schedule(c, aid, "R1_TECH")
        r1 = await c.post(f"/api/v1/interviews/{iid}/feedback", json=_fb_body(CTX["sid"]), headers=_h(CTX["hr"]))
        assert r1.status_code == 201
        r2 = await c.post(f"/api/v1/interviews/{iid}/feedback", json=_fb_body(CTX["sid"]), headers=_h(CTX["hr"]))
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "RMS-E-4223"  # INV-04


async def test_rating_out_of_bounds() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        iid = await _schedule(c, aid, "R1_TECH")
        r = await c.post(f"/api/v1/interviews/{iid}/feedback",
                         json=_fb_body(CTX["sid"], rating=6.0), headers=_h(CTX["hr"]))
        assert r.status_code == 422


async def test_lead_panelist_can_submit() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        iid = await _schedule(c, aid, "R1_TECH", lead=IV_UID)
        r = await c.post(f"/api/v1/interviews/{iid}/feedback", json=_fb_body(CTX["sid"]), headers=_h(CTX["iv"]))
        assert r.status_code == 201, r.text


async def test_non_panelist_forbidden() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        iid = await _schedule(c, aid, "R1_TECH", lead=IV_UID)  # HM is not on the panel
        r = await c.post(f"/api/v1/interviews/{iid}/feedback", json=_fb_body(CTX["sid"]), headers=_h(CTX["hm"]))
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_prior_feedback_inv06_chain() -> None:
    async with _client() as c:
        hr = CTX["hr"]
        aid = await _shortlisted_app(c)
        # Scheduling R1 auto-advances SHORTLISTED -> INTERVIEW_R1. After exact-round feedback,
        # scheduling R2 auto-advances INTERVIEW_R1 -> INTERVIEW_R2.
        r1 = await _schedule(c, aid, "R1_TECH")
        fb = await c.post(f"/api/v1/interviews/{r1}/feedback",
                          json=_fb_body(CTX["sid"], rec="SELECT"), headers=_h(hr))
        assert fb.status_code == 201, fb.text
        r2 = await _schedule(c, aid, "R2_TECH")
        current = await c.get(f"/api/v1/applications/{aid}", headers=_h(hr))
        assert current.json()["data"]["current_stage"] == "INTERVIEW_R2"
        # prior-feedback for R2 must surface R1 (INV-06)
        pf = await c.get(f"/api/v1/interviews/{r2}/prior-feedback", headers=_h(hr))
        assert pf.status_code == 200, pf.text
        rounds = [x["round"] for x in pf.json()["data"]]
        assert "R1_TECH" in rounds and "R2_TECH" not in rounds


async def test_prior_feedback_empty_for_r1() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        iid = await _schedule(c, aid, "R1_TECH")
        pf = await c.get(f"/api/v1/interviews/{iid}/prior-feedback", headers=_h(CTX["hr"]))
        assert pf.status_code == 200
        assert pf.json()["data"] == []


async def test_current_round_feedback_required_before_next_round() -> None:
    """A scheduled next round alone must not bypass feedback for the round being left."""
    async with _client() as c:
        hr = CTX["hr"]
        aid = await _shortlisted_app(c)
        r1 = await _schedule(c, aid, "R1_TECH")
        await _schedule(c, aid, "R2_TECH")  # saved, but auto-advance is deferred without R1 feedback

        current = await c.get(f"/api/v1/applications/{aid}", headers=_h(hr))
        assert current.json()["data"]["current_stage"] == "INTERVIEW_R1"

        blocked = await c.post(
            f"/api/v1/applications/{aid}/transition",
            headers=_h(hr),
            json={"action": "ADVANCE", "comment": "try to skip feedback", "target_stage": "INTERVIEW_R2"},
        )
        assert blocked.status_code == 422
        assert "feedback" in blocked.json()["error"]["message"].lower()

        saved = await c.post(
            f"/api/v1/interviews/{r1}/feedback",
            json=_fb_body(CTX["sid"], rec="SELECT"),
            headers=_h(hr),
        )
        assert saved.status_code == 201, saved.text
        advanced = await c.post(
            f"/api/v1/applications/{aid}/transition",
            headers=_h(hr),
            json={"action": "ADVANCE", "comment": "R1 complete", "target_stage": "INTERVIEW_R2"},
        )
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["data"]["current_stage"] == "INTERVIEW_R2"
