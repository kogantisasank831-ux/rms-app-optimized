"""/skills router — Skill Master import (ADMIN/HR) + typeahead (any authenticated)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_roles
from app.core.errors import ValidationError
from app.models.user import User
from app.services import skill_service

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillPayload(BaseModel):
    skill_name: str = Field(min_length=1, max_length=120)
    skill_category: str | None = Field(default=None, max_length=80)
    aliases: list[str] = Field(default_factory=list)

_XLSX_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",  # some browsers send this for .xlsx
}


@router.post("/import")
async def import_skills(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "HR")),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise ValidationError("Only .xlsx files are accepted", code="RMS-E-4001")
    data = await file.read()
    result = await skill_service.import_xlsx(db, data, user.user_id)
    return {"success": True, "data": result}


@router.post("")
async def create_skill(
    body: SkillPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "HR")),
) -> dict:
    row = await skill_service.create_skill(
        db, body.skill_name, body.skill_category, body.aliases, user.user_id
    )
    return {"success": True, "data": row}


@router.patch("/{skill_id}")
async def update_skill(
    body: SkillPayload,
    skill_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "HR")),
) -> dict:
    row = await skill_service.update_skill(
        db, skill_id, body.skill_name, body.skill_category, body.aliases, user.user_id
    )
    return {"success": True, "data": row}


@router.get("")
async def list_skills(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    rows, meta = await skill_service.list_skills(db, q, page, limit)
    return {"success": True, "data": rows, "meta": meta}
