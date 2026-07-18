"""/candidates router — intake (multipart CV) + role-scoped read."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_roles
from app.core.errors import ValidationError
from app.models.user import User
from app.schemas.candidate import CandidateCreate
from app.services import candidate_service

router = APIRouter(prefix="/candidates", tags=["candidates"])

_READ_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")
_WRITE_ROLES = ("ADMIN", "HR")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_candidate(
    payload: str = Form(..., description="JSON string of candidate fields"),
    cv_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> dict:
    try:
        parsed = CandidateCreate.model_validate_json(payload)
    except PydanticValidationError as exc:
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        raise ValidationError("Invalid candidate payload", code="RMS-E-4001", details=details) from exc
    data = await cv_file.read()
    result = await candidate_service.create_candidate(
        db, user, parsed, cv_file.filename or "cv", cv_file.content_type or "", data
    )
    return {"success": True, "data": result}


@router.get("")
async def list_candidates(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    items, meta = await candidate_service.list_candidates(db, user, page=page, limit=limit)
    return {"success": True, "data": items, "meta": meta}


@router.get("/{candidate_id}")
async def get_candidate(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    data = await candidate_service.get_candidate(db, user, candidate_id)
    return {"success": True, "data": data}
