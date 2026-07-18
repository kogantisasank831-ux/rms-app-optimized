"""T-202 tests — RRF state machine (G1-G5) + invariants INV-01/02/03/07/08. Live PG."""
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


def _bu_id() -> int:
    url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
    with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        return cur.fetchone()[0]


BU_ID = _bu_id()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


async def _token(c, creds) -> str:
    r = await c.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def _first_skill_id(c, t) -> int:
    r = await c.get("/api/v1/skills?limit=1", headers=_h(t))
    return r.json()["data"][0]["skill_id"]


async def _create_rrf(c, t, *, essential: bool = True) -> str:
    sid = await _first_skill_id(c, t)
    payload = {
        "position_title": "Solace Engineer", "positions_count": 1,
        "assignment_location": "Offshore (India)", "justification": "billable migration",
        "project_name": "Smart Load", "project_type": "T_AND_M",
        "needed_by_date": "2026-09-01", "min_experience_years": 3, "bu_id": BU_ID,
        "skills": [{"skill_id": sid, "req_type": "ESSENTIAL" if essential else "DESIRED", "priority": 5}],
    }
    r = await c.post("/api/v1/rrfs", json=payload, headers=_h(t))
    assert r.status_code == 201, r.text
    return r.json()["data"]["rrf_id"]


async def _tr(c, t, rid, action, comment="ok"):
    return await c.post(f"/api/v1/rrfs/{rid}/transition",
                        json={"action": action, "comment": comment}, headers=_h(t))


async def test_full_lifecycle() -> None:
    """G1 submit -> G2 approve -> G5 hold/resume -> G3 request_cancel -> G4 confirm_cancel."""
    async with _client() as c:
        hm = await _token(c, HM)
        bu = await _token(c, BUHEAD)
        hr = await _token(c, HR)
        rid = await _create_rrf(c, hm)

        r = await _tr(c, hm, rid, "SUBMIT", "please review")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "PENDING_APPROVAL"

        r = await _tr(c, bu, rid, "APPROVE", "budget ok")
        assert r.json()["data"]["status"] == "APPROVED", r.text

        r = await _tr(c, hr, rid, "HOLD", "pause sourcing")
        assert r.json()["data"]["status"] == "ON_HOLD"

        r = await _tr(c, hr, rid, "RESUME", "resume sourcing")
        assert r.json()["data"]["status"] == "APPROVED"  # INV-03 returns to held_from_status

        r = await _tr(c, hm, rid, "REQUEST_CANCEL", "role no longer needed")
        assert r.json()["data"]["status"] == "CANCEL_REQUESTED"  # INV-08 step 1

        r = await _tr(c, bu, rid, "CONFIRM_CANCEL", "confirmed")
        assert r.json()["data"]["status"] == "CANCELLED"  # INV-08 step 2

        # INV-02: a history row per transition (6 transitions)
        url = "postgresql://" + settings.DATABASE_URL.split("://", 1)[1].replace("+asyncpg", "")
        with psycopg.connect(url, options=f"-c search_path={settings.PG_SCHEMA},public") as cx, cx.cursor() as cur:
            cur.execute("SELECT count(*) FROM rrf_status_history WHERE rrf_id = %s", (rid,))
            assert cur.fetchone()[0] == 6
            cur.execute(
                "SELECT count(*) FROM audit_logs WHERE entity_type='RRF' AND entity_id=%s AND action LIKE 'TRANSITION:%%'",
                (rid,),
            )
            assert cur.fetchone()[0] == 6


async def test_submit_requires_essential_skill() -> None:
    async with _client() as c:
        hm = await _token(c, HM)
        rid = await _create_rrf(c, hm, essential=False)  # only a DESIRED skill
        r = await _tr(c, hm, rid, "SUBMIT", "review")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4221"


async def test_comment_required_whitespace() -> None:
    """INV-01 enforced server-side even when the string is non-empty whitespace."""
    async with _client() as c:
        hm = await _token(c, HM)
        rid = await _create_rrf(c, hm)
        r = await _tr(c, hm, rid, "SUBMIT", "   ")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4222"


async def test_hr_cannot_approve() -> None:
    """INV-07-adjacent: approve is BU_HEAD/ADMIN only."""
    async with _client() as c:
        hm = await _token(c, HM)
        hr = await _token(c, HR)
        rid = await _create_rrf(c, hm)
        await _tr(c, hm, rid, "SUBMIT", "review")
        r = await _tr(c, hr, rid, "APPROVE", "trying")
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_invalid_transition_approve_from_draft() -> None:
    async with _client() as c:
        hm = await _token(c, HM)
        bu = await _token(c, BUHEAD)
        rid = await _create_rrf(c, hm)  # stays DRAFT
        r = await _tr(c, bu, rid, "APPROVE", "too early")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4221"
