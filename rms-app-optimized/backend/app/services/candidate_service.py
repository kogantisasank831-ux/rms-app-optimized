"""candidate_service — candidate intake (CV -> MinIO + text extract), read with presigned CV url.

Intake order guards against orphans: validate -> dedupe email -> upload CV -> insert row -> audit.
If the upload fails, no DB row is written (LLD 8: candidate create is transactional wrt the PUT).
"""
from __future__ import annotations

import datetime
import re
import uuid

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, ValidationError
from app.models.candidate import Candidate
from app.models.user import User
from app.repositories import candidate_repo
from app.services import audit_service, avatar_service, storage_service
from app.utils import pagination
from app.utils.cv_text_extract import extract_text

_ALLOWED_EXT = {"pdf", "docx"}
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _validate_file(filename: str, data: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in _ALLOWED_EXT:
        raise ValidationError("CV must be a .pdf or .docx file", code="RMS-E-4001")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ValidationError(f"CV exceeds {settings.MAX_UPLOAD_MB} MB limit", code="RMS-E-4001")
    if len(data) == 0:
        raise ValidationError("CV file is empty", code="RMS-E-4001")
    return ext


def _object_key(candidate_id: uuid.UUID, filename: str, now: datetime.datetime) -> str:
    safe = _SAFE.sub("_", filename).strip("_") or "cv"
    return f"{storage_service.CV_PREFIX}{now.year}/{now.month:02d}/{candidate_id}_{safe}"


async def create_candidate(
    db: AsyncSession, user: User, payload, filename: str, content_type: str, data: bytes
) -> dict:
    _validate_file(filename, data)

    if await candidate_repo.get_by_email(db, payload.email) is not None:
        raise ConflictError(f"A candidate with email {payload.email} already exists", code="RMS-E-4091")

    candidate_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    key = _object_key(candidate_id, filename, now)

    cv_text = await run_in_threadpool(extract_text, filename, data)

    # upload first; if this raises StorageError no DB row is created
    await storage_service.put_object(
        key, data, content_type or "application/octet-stream",
        metadata={"entity-type": "CANDIDATE", "entity-id": str(candidate_id),
                  "uploaded-by": str(user.user_id)},
    )

    candidate = Candidate(
        candidate_id=candidate_id,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        total_experience_years=payload.total_experience_years,
        current_company=payload.current_company,
        notice_period_days=payload.notice_period_days,
        current_ctc=payload.current_ctc,
        expected_ctc=payload.expected_ctc,
        source=payload.source,
        cv_object_key=key,
        cv_file_name=filename,
        cv_text=cv_text or None,
        created_by=user.user_id,
    )
    db.add(candidate)
    await db.flush()
    await audit_service.record(
        db, entity_type="CANDIDATE", entity_id=str(candidate_id), action="CREATE",
        performed_by=user.user_id,
        after_state={"email": payload.email, "cv_object_key": key},
    )
    await db.commit()

    return {
        "candidate_id": str(candidate_id),
        "cv_object_key": key,
        "cv_text_extracted": bool(cv_text),
    }


def _list_item(c: Candidate) -> dict:
    return {
        "candidate_id": str(c.candidate_id),
        "full_name": c.full_name,
        "email": c.email,
        "source": c.source,
        "total_experience_years": float(c.total_experience_years) if c.total_experience_years is not None else None,
        "current_company": c.current_company,
        "cv_file_name": c.cv_file_name,
        "created_at": c.created_at,
    }


async def list_candidates(db: AsyncSession, user: User, *, page: int, limit: int) -> tuple[list[dict], dict]:
    p = pagination.resolve(page, limit)
    hm_id = user.user_id if user.role_code == "HIRING_MANAGER" else None
    rows, total = await candidate_repo.list_scoped(db, hm_user_id=hm_id, limit=p.limit, offset=p.offset)
    items = []
    for c in rows:
        item = _list_item(c)
        item["photo_icon_url"] = await avatar_service.url_for(c.photo_icon_key)  # small avatar for the row
        items.append(item)
    return items, pagination.meta(p, total)


async def get_candidate(db: AsyncSession, user: User, candidate_id: uuid.UUID) -> dict:
    from app.core.errors import ForbiddenError, NotFoundError

    c = await candidate_repo.get_by_id(db, candidate_id)
    if c is None:
        raise NotFoundError("Candidate not found", code="RMS-E-4041")

    if user.role_code == "HIRING_MANAGER":
        # HM may see only candidates linked to their own RRFs
        scoped, _ = await candidate_repo.list_scoped(db, hm_user_id=user.user_id, limit=1000, offset=0)
        if candidate_id not in {x.candidate_id for x in scoped}:
            raise ForbiddenError("Not permitted to access this candidate", code="RMS-E-4031")

    cv_url = await storage_service.presigned_get_url(c.cv_object_key, ensure_exists=False)
    item = _list_item(c)
    item.update({
        "phone": c.phone,
        "notice_period_days": c.notice_period_days,
        "current_ctc": c.current_ctc,
        "expected_ctc": c.expected_ctc,
        "cv_object_key": c.cv_object_key,
        "cv_download_url": cv_url,
        "cv_text": c.cv_text,
        "parsed_cv": c.parsed_cv,
        "created_by": str(c.created_by),
        **await avatar_service.urls(c.photo_icon_key, c.photo_object_key),
    })
    return item
