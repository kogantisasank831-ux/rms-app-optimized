"""T-105 smoke tests — Skill Master import + typeahead. Uses seeded skills + an in-memory xlsx."""
from __future__ import annotations

import io

import httpx
import openpyxl
from httpx import ASGITransport

from app.main import create_app

app = create_app()
transport = ASGITransport(app=app)
BASE = "http://test"
HR = {"email": "hr@rms.local", "password": "Passw0rd!23"}
CANDIDATE = {"email": "candidate@rms.local", "password": "Passw0rd!23"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


async def _token(c: httpx.AsyncClient, creds: dict) -> str:
    r = await c.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _make_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["skill_name", "skill_category", "aliases"])
    ws.append(["GraphQL", "API", "graph-ql,gql"])          # new
    ws.append(["Java", "Language", "Core Java, J2EE"])      # existing -> update
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def test_typeahead_by_name() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        r = await c.get("/api/v1/skills?q=aws", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert "meta" in body and body["meta"]["limit"] == 20
        names = [s["skill_name"] for s in body["data"]]
        assert any("AWS" in n for n in names)


async def test_typeahead_by_alias() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        # 'springboot' is an alias of seeded 'Spring Boot'
        r = await c.get("/api/v1/skills?q=springboot", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        names = [s["skill_name"] for s in r.json()["data"]]
        assert "Spring Boot" in names


async def test_pagination_limit() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        r = await c.get("/api/v1/skills?limit=3", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["limit"] == 3
        assert len(body["data"]) <= 3


async def test_list_requires_auth() -> None:
    async with _client() as c:
        r = await c.get("/api/v1/skills?q=aws")
        assert r.status_code == 401


async def test_import_forbidden_for_candidate() -> None:
    async with _client() as c:
        token = await _token(c, CANDIDATE)
        files = {"file": ("skills.xlsx", _make_xlsx(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = await c.post("/api/v1/skills/import", files=files,
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_import_rejects_non_xlsx() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        files = {"file": ("skills.csv", b"a,b,c", "text/csv")}
        r = await c.post("/api/v1/skills/import", files=files,
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422


async def test_import_success_and_findable() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        files = {"file": ("skills.xlsx", _make_xlsx(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = await c.post("/api/v1/skills/import", files=files,
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["rows"] == 2
        assert data["inserted"] + data["updated"] == 2
        # the new skill is now searchable
        r2 = await c.get("/api/v1/skills?q=graphql", headers={"Authorization": f"Bearer {token}"})
        assert "GraphQL" in [s["skill_name"] for s in r2.json()["data"]]
