"""router: /users — directory lookup for panelist selection and assignment pickers.

Read-only. Returns active users (excluding pure CANDIDATE accounts) so HR/Admin can build
interview panels (INV-05). Paginated per INV-11.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_roles
from app.models.user import Role, User
from app.services import avatar_service, user_service
from app.utils import pagination

router = APIRouter(prefix="/users", tags=["users"])

_READ_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")
_ADMIN_ONLY = ("ADMIN",)


class CreateUserPayload(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(description="role_code, e.g. INTERVIEWER")
    designation: str | None = Field(default=None, max_length=80)
    password: str | None = Field(default=None, max_length=120)


class UpdateUserPayload(BaseModel):
    """Admin edit — every field optional; only provided ones change. `is_active` alone keeps
    the previous activate/deactivate behaviour working."""
    full_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    designation: str | None = Field(default=None, max_length=80)
    role: str | None = Field(default=None, description="role_code, e.g. INTERVIEWER")
    is_active: bool | None = None


@router.get("")
async def list_users(
    role: str | None = Query(default=None, description="Filter by role_code, e.g. INTERVIEWER"),
    q: str | None = Query(default=None, description="Case-insensitive match on name or email"),
    include_inactive: bool = Query(default=False, description="Include deactivated users (admin views)"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    p = pagination.resolve(page, limit)
    base = (
        select(User, Role.role_code, Role.role_name)
        .join(Role, User.role_id == Role.role_id)
        .where(Role.role_code != "CANDIDATE")
    )
    if not include_inactive:
        base = base.where(User.is_active.is_(True))
    if role:
        base = base.where(Role.role_code == role)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(func.lower(User.full_name).like(like) | func.lower(User.email).like(like))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.order_by(User.full_name).limit(p.limit).offset(p.offset))).all()
    data = [
        {
            "user_id": str(u.user_id),
            "full_name": u.full_name,
            "email": u.email,
            "role": role_code,
            "role_name": role_name,
            "designation": u.designation,
            "is_active": u.is_active,
            # small icon only for the list; presign is skipped-existence for speed
            "photo_icon_url": await avatar_service.url_for(u.photo_icon_key),
            "photo_url": await avatar_service.url_for(u.photo_object_key),
        }
        for (u, role_code, role_name) in rows
    ]
    return {"success": True, "data": data, "meta": pagination.meta(p, total)}


@router.get("/roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*_ADMIN_ONLY)),
) -> dict:
    """Assignable roles for the new-employee form (excludes CANDIDATE)."""
    return {"success": True, "data": await user_service.list_roles(db)}


@router.post("")
async def create_user(
    body: CreateUserPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ADMIN_ONLY)),
) -> dict:
    """Add an employee to the directory (selectable as a panelist thereafter)."""
    row = await user_service.create_user(
        db, email=body.email, full_name=body.full_name, role_code=body.role,
        designation=body.designation, password=body.password, actor_id=user.user_id,
    )
    return {"success": True, "data": row}


@router.post("/me/photo")
async def set_my_photo(
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Any signed-in user sets their own profile photo (used as their avatar everywhere)."""
    data = await photo.read()
    row = await user_service.set_photo(
        db, user_id=user.user_id, actor_id=user.user_id,
        data=data, content_type=photo.content_type or "",
    )
    return {"success": True, "data": row}


@router.post("/{user_id}/photo")
async def set_user_photo(
    user_id: uuid.UUID = Path(...),
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ADMIN_ONLY)),
) -> dict:
    """ADMIN sets any user's profile photo from the admin panel."""
    data = await photo.read()
    row = await user_service.set_photo(
        db, user_id=user_id, actor_id=user.user_id,
        data=data, content_type=photo.content_type or "",
    )
    return {"success": True, "data": row}


@router.patch("/{user_id}")
async def update_user(
    body: UpdateUserPayload,
    user_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ADMIN_ONLY)),
) -> dict:
    """ADMIN edit of a user's details. Sending only `is_active` toggles activation
    (deactivated users drop out of panel pickers); other fields update name/email/role."""
    row = await user_service.admin_update(
        db, user_id=user_id, actor_id=user.user_id,
        full_name=body.full_name, email=body.email, designation=body.designation,
        role_code=body.role, is_active=body.is_active,
    )
    return {"success": True, "data": row}
