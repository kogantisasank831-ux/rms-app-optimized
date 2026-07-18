"""Password hashing (bcrypt) + JWT create/verify (HS256, 8h, 60s clock-skew leeway)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.errors import AuthError

_ROUNDS = 12
_ALGO = "HS256"
_LEEWAY_SECONDS = 60  # clock-skew tolerance


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, role: str) -> tuple[str, int]:
    """Return (jwt, expires_in_seconds). Claims: sub, role, iat, exp."""
    expires_in = settings.JWT_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGO)
    return token, expires_in


def decode_token(token: str) -> dict:
    """Decode + verify a JWT. Raises AuthError (401) on expiry/invalid."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[_ALGO],
            options={"leeway": _LEEWAY_SECONDS},
        )
    except ExpiredSignatureError as exc:
        raise AuthError("Token expired", code="RMS-E-4012") from exc
    except JWTError as exc:
        raise AuthError("Invalid authentication token", code="RMS-E-4013") from exc
