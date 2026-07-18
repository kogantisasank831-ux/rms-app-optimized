"""T-301 tests — interview scheduling (panel 1..5 INV-05), my-interviews, cancel, RBAC. Live PG.

Module setup builds an APPROVED RRF + a SHORTLISTED application (the point where R1 is scheduled).
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
FUTURE_START = "2026-08-01T09:30:00Z"
FUTURE_END = "2026-08-01T10:30:00Z"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _docx() -> bytes:
    d = docx.Document()
    d.add_paragraph("Experienced AWS Java Solace engineer")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _db():
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    return psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public")


def _ids() -> tuple[int, str, str]:
    """bu_id, interviewer user_id, hr user_id (panelists)."""
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        bu = cur.fetchone()[0]
        cur.execute("SELECT user_id FROM users WHERE lower(email)='interviewer@rms.local'")
        iv = str(cur.fetchone()[0])
        cur.execute("SELECT user_id FROM users WHERE lower(email)='hr@rms.local'")
        hr = str(cur.fetchone()[0])
    return bu, iv, hr


BU_ID, IV_UID, HR_UID = _ids()


async def _setup() -> dict:
    async with _client() as c:
        async def tok(cr):
            r = await c.post("/api/v1/auth/login", json=cr)
            return r.json()["data"]["access_token"]

        hr, hm, bu, ivt = await tok(HR), await tok(HM), await tok(BUHEAD), await tok(INTERVIEWER)
        sid = (await c.get("/api/v1/skills?limit=1", headers=_h(hr))).json()["data"][0]["skill_id"]
        rid = (await c.post("/api/v1/rrfs", headers=_h(hm), json={
            "position_title": "Interview Test Role", "positions_count": 3,
            "assignment_location": "Offshore (India)", "justification": "iv tests",
            "project_name": "Smart Load", "project_type": "T_AND_M",
            "needed_by_date": "2026-10-01", "min_experience_years": 3, "bu_id": BU_ID,
            "skills": [{"skill_id": sid, "req_type": "ESSENTIAL", "priority": 5}],
        })).json()["data"]["rrf_id"]
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(hm), json={"action": "SUBMIT", "comment": "go"})
        await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(bu), json={"action": "APPROVE", "comment": "ok"})
        return {"hr": hr, "hm": hm, "iv": ivt, "rid": rid}


CTX = asyncio.run(_setup())


async def _shortlisted_app(c) -> str:
    payload = {"full_name": "IV Cand", "email": f"iv-{uuid.uuid4().hex[:10]}@example.com", "source": "PORTAL"}
    files = {"cv_file": ("cv.docx", _docx(),
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    cid = (await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)},
                        files=files, headers=_h(CTX["hr"]))).json()["data"]["candidate_id"]
    aid = (await c.post("/api/v1/applications", headers=_h(CTX["hr"]),
                        json={"rrf_id": CTX["rid"], "candidate_id": cid})).json()["data"]["application_id"]
    # SCREENING -> SHORTLISTED
    await c.post(f"/api/v1/applications/{aid}/transition", headers=_h(CTX["hr"]),
                 json={"action": "ADVANCE", "comment": "shortlist"})
    return aid


def _schedule_body(aid: str, panelists: list[dict]) -> dict:
    return {"application_id": aid, "round": "R1_TECH", "scheduled_start": FUTURE_START,
            "scheduled_end": FUTURE_END, "mode": "VIDEO", "meeting_link": "https://meet.example/x",
            "panelists": panelists}


async def test_schedule_with_panel() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        body = _schedule_body(aid, [{"user_id": IV_UID, "is_lead": True},
                                    {"user_id": HR_UID, "is_lead": False}])
        r = await c.post("/api/v1/interviews", json=body, headers=_h(CTX["hr"]))
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["status"] == "SCHEDULED"
        assert data["round"] == "R1_TECH"
        # Scheduling the next required round advances the pipeline and reports the authoritative
        # application stage in the same response used by the Kanban reconciliation flow.
        assert data["application_stage"] == "INTERVIEW_R1"
        current = await c.get(f"/api/v1/applications/{aid}", headers=_h(CTX["hr"]))
        assert current.status_code == 200
        assert current.json()["data"]["current_stage"] == "INTERVIEW_R1"
        assert len(data["panelists"]) == 2
        assert sum(p["is_lead"] for p in data["panelists"]) == 1


async def test_panel_size_zero_violation() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        r = await c.post("/api/v1/interviews", json=_schedule_body(aid, []), headers=_h(CTX["hr"]))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4224"  # INV-05


async def test_panel_size_six_violation() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        panel = [{"user_id": IV_UID, "is_lead": True}] + [{"user_id": HR_UID, "is_lead": False}] * 5
        r = await c.post("/api/v1/interviews", json=_schedule_body(aid, panel), headers=_h(CTX["hr"]))
        assert r.status_code == 422
        assert r.json()["error"]["code"] in ("RMS-E-4224", "RMS-E-4001")


async def test_no_lead_rejected() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        r = await c.post("/api/v1/interviews",
                         json=_schedule_body(aid, [{"user_id": IV_UID, "is_lead": False}]),
                         headers=_h(CTX["hr"]))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"


async def test_end_before_start_rejected() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        body = _schedule_body(aid, [{"user_id": IV_UID, "is_lead": True}])
        body["scheduled_end"] = FUTURE_START  # equal -> invalid
        r = await c.post("/api/v1/interviews", json=body, headers=_h(CTX["hr"]))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"


async def test_interviewer_sees_in_my() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        await c.post("/api/v1/interviews",
                     json=_schedule_body(aid, [{"user_id": IV_UID, "is_lead": True}]),
                     headers=_h(CTX["hr"]))
        r = await c.get("/api/v1/interviews/my", headers=_h(CTX["iv"]))
        assert r.status_code == 200, r.text
        app_ids = [x["application_id"] for x in r.json()["data"]]
        assert aid in app_ids


async def test_cancel_interview() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        iid = (await c.post("/api/v1/interviews",
                            json=_schedule_body(aid, [{"user_id": IV_UID, "is_lead": True}]),
                            headers=_h(CTX["hr"]))).json()["data"]["interview_id"]
        r = await c.patch(f"/api/v1/interviews/{iid}",
                          json={"action": "CANCEL", "comment": "candidate unavailable"},
                          headers=_h(CTX["hr"]))
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "CANCELLED"


async def test_interviewer_cannot_schedule() -> None:
    async with _client() as c:
        aid = await _shortlisted_app(c)
        r = await c.post("/api/v1/interviews",
                         json=_schedule_body(aid, [{"user_id": IV_UID, "is_lead": True}]),
                         headers=_h(CTX["iv"]))
        assert r.status_code == 403
