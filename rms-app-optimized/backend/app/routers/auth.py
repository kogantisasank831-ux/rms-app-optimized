"""/auth router — login (public) and current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.services import avatar_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    from app.services import auth_service

    data = await auth_service.login(db, payload.email, payload.password)
    return {"success": True, "data": data}


@router.get("/me", response_model=MeResponse)
async def me(current: User = Depends(get_current_user)) -> dict:
    return {
        "success": True,
        "data": {
            "user_id": str(current.user_id),
            "full_name": current.full_name,
            "email": current.email,
            "role": current.role_code,
            "designation": current.designation,
            **await avatar_service.urls(current.photo_icon_key, current.photo_object_key),
        },
    }
