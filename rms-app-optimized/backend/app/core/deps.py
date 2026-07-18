"""FastAPI dependencies: DB session, current user (JWT), role guard."""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories import user_repo

__all__ = ["get_db", "get_current_user", "require_roles"]

# auto_error=False so we raise our own envelope error instead of FastAPI's default 403
_bearer = HTTPBearer(auto_error=False, description="JWT from POST /api/v1/auth/login")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthError("Missing bearer token", code="RMS-E-4011")

    payload = decode_token(credentials.credentials)
    sub = payload.get("sub")
    try:
        user_id = uuid.UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise AuthError("Invalid token subject", code="RMS-E-4013") from exc

    user = await user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive", code="RMS-E-4011")
    return user


def require_roles(*role_codes: str) -> Callable[..., Awaitable[User]]:
    """Dependency factory: allow only the given role codes (server-enforced RBAC, LLD 7.1)."""
    allowed = set(role_codes)

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role_code not in allowed:
            raise ForbiddenError(
                f"Role {user.role_code} not permitted for this action",
                code="RMS-E-4031",
            )
        return user

    return _checker
