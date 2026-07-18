"""T-103 smoke tests — auth. Runs against the provided PG using seeded demo users."""
from __future__ import annotations

import httpx
from fastapi import Depends
from httpx import ASGITransport

from app.core.deps import require_roles
from app.main import create_app
from app.models.user import User

app = create_app()


# probe route to exercise require_roles (ADMIN-only)
@app.get("/api/v1/_admin_probe")
async def _admin_probe(user: User = Depends(require_roles("ADMIN"))) -> dict:
    return {"success": True, "data": {"role": user.role_code}}


transport = ASGITransport(app=app)
BASE = "http://test"
HR = {"email": "hr@rms.local", "password": "Passw0rd!23"}
ADMIN = {"email": "admin@rms.local", "password": "Passw0rd!23"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


async def _login(c: httpx.AsyncClient, creds: dict) -> str:
    r = await c.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def test_health_ok() -> None:
    async with _client() as c:
        r = await c.get("/api/v1/health")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["checks"]["db"] == "ok"


async def test_login_success() -> None:
    async with _client() as c:
        r = await c.post("/api/v1/auth/login", json=HR)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 480 * 60
        assert data["user"]["role"] == "HR"
        assert data["access_token"]


async def test_login_wrong_password() -> None:
    async with _client() as c:
        r = await c.post("/api/v1/auth/login", json={**HR, "password": "nope"})
        assert r.status_code == 401
        body = r.json()
        assert body["success"] is False
        assert body["error"]["code"] == "RMS-E-4011"


async def test_me_with_token() -> None:
    async with _client() as c:
        token = await _login(c, HR)
        r = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["data"]["email"] == "hr@rms.local"


async def test_me_without_token() -> None:
    async with _client() as c:
        r = await c.get("/api/v1/auth/me")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "RMS-E-4011"


async def test_me_bad_token() -> None:
    async with _client() as c:
        r = await c.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "RMS-E-4013"


async def test_require_roles_forbidden_for_hr() -> None:
    async with _client() as c:
        token = await _login(c, HR)
        r = await c.get("/api/v1/_admin_probe", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_require_roles_allows_admin() -> None:
    async with _client() as c:
        token = await _login(c, ADMIN)
        r = await c.get("/api/v1/_admin_probe", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["data"]["role"] == "ADMIN"
