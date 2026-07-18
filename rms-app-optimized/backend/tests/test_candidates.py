"""T-204 tests — candidate intake (CV -> MinIO + extract), read, RBAC. Live PG + MinIO."""
from __future__ import annotations

import io
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
INTERVIEWER = {"email": "interviewer@rms.local", "password": "Passw0rd!23"}
CV_MARKER = "AWS Java Solace microservices Oracle"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url=BASE)


async def _token(c, creds) -> str:
    r = await c.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _docx_bytes(text: str) -> bytes:
    d = docx.Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _uniq_email() -> str:
    return f"cand-{uuid.uuid4().hex[:10]}@example.com"


async def _create(c, token, *, email: str, filename: str = "cv.docx", data: bytes | None = None):
    import json
    payload = {"full_name": "Gaurav Panchal", "email": email, "total_experience_years": 4.5,
               "source": "PORTAL", "notice_period_days": 30}
    files = {
        "cv_file": (filename, data if data is not None else _docx_bytes(CV_MARKER),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }
    return await c.post("/api/v1/candidates", data={"payload": json.dumps(payload)}, files=files,
                        headers={"Authorization": f"Bearer {token}"})


async def test_create_extracts_text_and_uploads() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        r = await _create(c, token, email=_uniq_email())
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["cv_text_extracted"] is True
        assert data["cv_object_key"].startswith("cvs/")


async def test_detail_has_presigned_url_and_text() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        created = (await _create(c, token, email=_uniq_email())).json()["data"]
        r = await c.get(f"/api/v1/candidates/{created['candidate_id']}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["cv_download_url"].startswith("http")
        assert CV_MARKER.split()[0] in (body["cv_text"] or "")
    # presigned url actually downloads the CV
    async with httpx.AsyncClient() as raw:
        dl = await raw.get(body["cv_download_url"])
        assert dl.status_code == 200
        assert len(dl.content) > 0


async def test_list_excludes_cv_text() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        await _create(c, token, email=_uniq_email())
        r = await c.get("/api/v1/candidates?limit=5", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        for item in r.json()["data"]:
            assert "cv_text" not in item  # payload discipline (INV/perf)


async def test_duplicate_email_conflict() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        email = _uniq_email()
        r1 = await _create(c, token, email=email)
        assert r1.status_code == 201
        r2 = await _create(c, token, email=email)
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "RMS-E-4091"


async def test_invalid_extension_rejected() -> None:
    async with _client() as c:
        token = await _token(c, HR)
        r = await _create(c, token, email=_uniq_email(), filename="cv.txt", data=b"plain text cv")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RMS-E-4001"


async def test_hm_cannot_create() -> None:
    async with _client() as c:
        token = await _token(c, HM)
        r = await _create(c, token, email=_uniq_email())
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "RMS-E-4031"


async def test_interviewer_cannot_list() -> None:
    async with _client() as c:
        token = await _token(c, INTERVIEWER)
        r = await c.get("/api/v1/candidates", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


async def test_create_requires_auth() -> None:
    async with _client() as c:
        import json
        files = {"cv_file": ("cv.docx", _docx_bytes(CV_MARKER),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        r = await c.post("/api/v1/candidates",
                         data={"payload": json.dumps({"full_name": "X", "email": _uniq_email()})},
                         files=files)
        assert r.status_code == 401
