"""T-201 smoke tests — RRF CRUD + code generation + role scoping. Runs against live PG."""
from __future__ import annotations

import re

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


def _payload(skill_ids: list[int]) -> dict:
    return {
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
            {"skill_id": skill_ids[0], "req_type": "ESSENTIAL", "priority": 5},
            {"skill_id": skill_ids[1], "req_type": "DESIRED", "priority": 3},
        ],
    }


async def _create(c: httpx.AsyncClient, token: str) -> dict:
    ids = await _skill_ids(c, token)
    r = await c.post("/api/v1/rrfs", json=_payload(ids), headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def test_create_rrf_and_code_format() -> None:
    async with _client() as c:
        token = await _token(c, HM)
        data = await _create(c, token)
        assert data["status"] == "DRAFT"
        assert re.match(r"^RRF-\d{4}-\d{4}$", data["rrf_code"]), data["rrf_code"]


async def test_get_detail_has_skills() -> None:
    async with _client() as c:
        token = await _token(c, HM)
        created = await _create(c, token)
        r = await c.get(f"/api/v1/rrfs/{created['rrf_id']}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert len(body["skills"]) == 2
        assert body["skills"][0]["skill_name"]  # joined from skill_master
        assert body["positions_count"] == 2


async def test_hm_lists_own() -> None:
    async with _client() as c:
        token = await _token(c, HM)
        created = await _create(c, token)
        r = await c.get("/api/v1/rrfs?limit=100", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        codes = [x["rrf_code"] for x in r.json()["data"]]
        assert created["rrf_code"] in codes


async def test_bu_head_sees_own_bu() -> None:
    async with _client() as c:
        hm_token = await _token(c, HM)
        created = await _create(c, hm_token)
        bu_token = await _token(c, BUHEAD)
        # detail readable by BU head of that BU
        r = await c.get(f"/api/v1/rrfs/{created['rrf_id']}", headers={"Authorization": f"Bearer {bu_token}"})
        assert r.status_code == 200, r.text


async def test_interviewer_forbidden() -> None:
    async with _client() as c:
        token = await _token(c, INTERVIEWER)
        r = await c.get("/api/v1/rrfs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_hr_cannot_create() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        ids = await _skill_ids(c, token)
        r = await c.post("/api/v1/rrfs", json=_payload(ids), headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_create_invalid_bu() -> None:
    async with _client() as c:
        token = await _token(c, HM)
        ids = await _skill_ids(c, token)
        payload = {**_payload(ids), "bu_id": 999999}
        r = await c.post("/api/v1/rrfs", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"


async def test_update_title_while_draft() -> None:
    async with _client() as c:
        token = await _token(c, HM)
        created = await _create(c, token)
        r = await c.patch(
            f"/api/v1/rrfs/{created['rrf_id']}",
            json={"position_title": "Senior Solace Engineer"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["position_title"] == "Senior Solace Engineer"
