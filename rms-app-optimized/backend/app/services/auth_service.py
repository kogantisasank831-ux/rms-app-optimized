"""auth_service — credential verification, token issue, login auditing (INV-02)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories import user_repo
from app.services import audit_service, avatar_service


async def login(db: AsyncSession, email: str, password: str) -> dict:
    """Authenticate and return the login payload. Audits success and failure."""
    user = await user_repo.get_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        await audit_service.record(
            db,
            entity_type="USER",
            entity_id=email,
            action="LOGIN_FAILED",
            performed_by=user.user_id if user else None,
            after_state={"email": email, "reason": "invalid_credentials"},
        )
        await db.commit()
        raise AuthError("Invalid email or password", code="RMS-E-4011")

    token, expires_in = create_access_token(user.user_id, user.role_code)
    await audit_service.record(
        db,
        entity_type="USER",
        entity_id=str(user.user_id),
        action="LOGIN",
        performed_by=user.user_id,
        after_state={"email": user.email, "role": user.role_code},
    )
    await db.commit()

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": await _user_public(user),
    }


async def _user_public(user: User) -> dict:
    return {
        "user_id": str(user.user_id),
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role_code,
        "designation": user.designation,
        **await avatar_service.urls(user.photo_icon_key, user.photo_object_key),
    }
