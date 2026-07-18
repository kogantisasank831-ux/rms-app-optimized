"""T-104 smoke tests — presigned file access. Uses the seeded offer template object."""
from __future__ import annotations

import httpx
from httpx import ASGITransport

from app.main import create_app

app = create_app()
transport = ASGITransport(app=app)
BASE = "http://test"
TEMPLATE_KEY = "templates/offer_template_v1.html"
ADMIN = {"email": "admin@rms.local", "password": "Passw0rd!23"}
HR = {"email": "hr@rms.local", "password": "Passw0rd!23"}
BUHEAD = {"email": "buhead@rms.local", "password": "Passw0rd!23"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


async def _token(c: httpx.AsyncClient, creds: dict) -> str:
    r = await c.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def test_presign_and_download() -> None:
    async with _client() as c:
        token = await _token(c, ADMIN)
        r = await c.get(f"/api/v1/files/presign?object_key={TEMPLATE_KEY}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        url = r.json()["data"]["download_url"]
        assert url.startswith("http")
    # presigned url is public + time-limited; fetch it directly (no app transport)
    async with httpx.AsyncClient() as raw:
        dl = await raw.get(url)
        assert dl.status_code == 200
        assert "<html" in dl.text.lower()


async def test_presign_requires_auth() -> None:
    async with _client() as c:
        r = await c.get(f"/api/v1/files/presign?object_key={TEMPLATE_KEY}")
        assert r.status_code == 401


async def test_presign_forbidden_for_non_admin_roles() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        r = await c.get(f"/api/v1/files/presign?object_key={TEMPLATE_KEY}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_presign_rejects_bad_prefix() -> None:
    async with _client() as c:
        token = await _token(c, ADMIN)
        r = await c.get("/api/v1/files/presign?object_key=secret/passwd",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"


async def test_presign_rejects_private_object_prefixes() -> None:
    async with _client() as c:
        token = await _token(c, ADMIN)
        r = await c.get("/api/v1/files/presign?object_key=cvs/2026/07/candidate.pdf",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"
