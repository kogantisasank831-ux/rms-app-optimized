"""T-306 tests — offers, fixed-template letter (INV-10), G16/G17 + G11/G12/G13. Live PG + MinIO.

The application is placed at the OFFER stage via a direct DB update (the interview->OFFER chain
is covered by T-301/T-303); these tests focus on offer logic.
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


def _bu_id() -> int:
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT bu_id FROM business_units ORDER BY bu_id LIMIT 1")
        return cur.fetchone()[0]


BU_ID = _bu_id()


async def _setup() -> dict:
    async with _client() as c:
        async def tok(cr):
            r = await c.post("/api/v1/auth/login", json=cr)
            return r.json()["data"]["access_token"]

        hr, hm, bu = await tok(HR), await tok(HM), await tok(BUHEAD)
        sid = (await c.get("/api/v1/skills?limit=1", headers=_h(hr))).json()["data"][0]["skill_id"]
        ctx = {"hr": hr, "hm": hm, "bu": bu, "sid": sid}
        # shared RRF with plenty of positions so non-joining tests never auto-close it
        ctx["rid"] = await _approved_rrf(c, ctx, positions_count=10)
        return ctx


async def _approved_rrf(c, ctx: dict, positions_count: int) -> str:
    rid = (await c.post("/api/v1/rrfs", headers=_h(ctx["hm"]), json={
        "position_title": "Offer Test Role", "positions_count": positions_count,
        "assignment_location": "Offshore (India)", "justification": "offer tests",
        "project_name": "Smart Load", "project_type": "T_AND_M",
        "needed_by_date": "2026-10-01", "min_experience_years": 3, "bu_id": BU_ID,
        "skills": [{"skill_id": ctx["sid"], "req_type": "ESSENTIAL", "priority": 5}],
    })).json()["data"]["rrf_id"]
    await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(ctx["hm"]), json={"action": "SUBMIT", "comment": "go"})
    await c.post(f"/api/v1/rrfs/{rid}/transition", headers=_h(ctx["bu"]), json={"action": "APPROVE", "comment": "ok"})
    return rid


CTX = asyncio.run(_setup())


async def _app(c, *, at_offer: bool, rid: str | None = None) -> str:
    rid = rid or CTX["rid"]
    payload = {"full_name": "Offer Cand", "email": f"of-{uuid.uuid4().hex[:10]}@example.com", "source": "PORTAL"}
    files = {"cv_file": ("cv.docx", _docx(),
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    cid = (await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)},
                        files=files, headers=_h(CTX["hr"]))).json()["data"]["candidate_id"]
    aid = (await c.post("/api/v1/applications", headers=_h(CTX["hr"]),
                        json={"rrf_id": rid, "candidate_id": cid})).json()["data"]["application_id"]
    if at_offer:
        with _db() as cx, cx.cursor() as cur:
            cur.execute("UPDATE applications SET current_stage='OFFER' WHERE application_id=%s", (aid,))
            cx.commit()
    return aid


def _offer_body(aid: str) -> dict:
    return {"application_id": aid, "designation": "Senior Engineer", "ctc_annual": "INR 30,00,000",
            "joining_date": "2026-09-15", "work_location": "Kolkata", "valid_until": "2026-08-31"}


async def _make_offer(c, aid) -> str:
    r = await c.post("/api/v1/offers", json=_offer_body(aid), headers=_h(CTX["hr"]))
    assert r.status_code == 201, r.text
    return r.json()["data"]["offer_id"]


async def test_create_requires_offer_stage() -> None:
    async with _client() as c:
        aid = await _app(c, at_offer=False)  # stays at SCREENING
        r = await c.post("/api/v1/offers", json=_offer_body(aid), headers=_h(CTX["hr"]))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"


async def test_release_requires_letter() -> None:
    async with _client() as c:
        oid = await _make_offer(c, await _app(c, at_offer=True))
        r = await c.post(f"/api/v1/offers/{oid}/transition",
                         json={"action": "RELEASE", "comment": "release"}, headers=_h(CTX["hr"]))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4221"  # INV-10 letter required


async def test_generate_letter_and_full_accept_join() -> None:
    """G16 release -> G17 accept -> G11 OFFER_ACCEPTED -> G12 JOINED (+RRF auto-close)."""
    async with _client() as c:
        rid1 = await _approved_rrf(c, CTX, positions_count=1)  # dedicated RRF that will auto-close
        aid = await _app(c, at_offer=True, rid=rid1)
        oid = await _make_offer(c, aid)

        gl = await c.post(f"/api/v1/offers/{oid}/generate-letter", headers=_h(CTX["hr"]))
        assert gl.status_code == 200, gl.text
        key = gl.json()["data"]["letter_object_key"]
        assert key.startswith("offers/") and key.rsplit(".", 1)[-1] in ("pdf", "html")  # R3 fallback ok
        assert gl.json()["data"]["download_url"].startswith("http")

        rel = await c.post(f"/api/v1/offers/{oid}/transition",
                           json={"action": "RELEASE", "comment": "released to candidate"}, headers=_h(CTX["hr"]))
        assert rel.json()["data"]["status"] == "RELEASED"

        acc = await c.post(f"/api/v1/offers/{oid}/transition",
                           json={"action": "ACCEPT", "comment": "candidate accepted"}, headers=_h(CTX["hr"]))
        assert acc.json()["data"]["status"] == "ACCEPTED"

        # G11: application moved to OFFER_ACCEPTED
        appd = await c.get(f"/api/v1/applications/{aid}", headers=_h(CTX["hr"]))
        assert appd.json()["data"]["current_stage"] == "OFFER_ACCEPTED"

        # G12: mark joined
        mj = await c.post(f"/api/v1/applications/{aid}/transition",
                          json={"action": "MARK_JOINED", "comment": "joined"}, headers=_h(CTX["hr"]))
        assert mj.status_code == 200, mj.text
        assert mj.json()["data"]["current_stage"] == "JOINED"
        assert mj.json()["data"]["status"] == "HIRED"

    # RRF auto-closed (its single position filled)
    with _db() as cx, cx.cursor() as cur:
        cur.execute("SELECT status, positions_filled FROM rrf WHERE rrf_id=%s", (rid1,))
        status_, filled = cur.fetchone()
    assert filled >= 1 and status_ == "CLOSED"


async def test_decline_rejects_application() -> None:
    async with _client() as c:
        aid = await _app(c, at_offer=True)
        oid = await _make_offer(c, aid)
        await c.post(f"/api/v1/offers/{oid}/generate-letter", headers=_h(CTX["hr"]))
        await c.post(f"/api/v1/offers/{oid}/transition",
                     json={"action": "RELEASE", "comment": "release"}, headers=_h(CTX["hr"]))
        dec = await c.post(f"/api/v1/offers/{oid}/transition",
                           json={"action": "DECLINE", "comment": "candidate declined"}, headers=_h(CTX["hr"]))
        assert dec.json()["data"]["status"] == "DECLINED"
        appd = await c.get(f"/api/v1/applications/{aid}", headers=_h(CTX["hr"]))
        assert appd.json()["data"]["status"] == "REJECTED"  # G13


async def test_duplicate_offer_conflict() -> None:
    async with _client() as c:
        aid = await _app(c, at_offer=True)
        await _make_offer(c, aid)
        r = await c.post("/api/v1/offers", json=_offer_body(aid), headers=_h(CTX["hr"]))
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "RMS-E-4091"


async def test_hm_cannot_create_offer() -> None:
    async with _client() as c:
        aid = await _app(c, at_offer=True)
        r = await c.post("/api/v1/offers", json=_offer_body(aid), headers=_h(CTX["hm"]))
        assert r.status_code == 403
