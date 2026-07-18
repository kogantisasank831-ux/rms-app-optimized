"""AppError hierarchy + error-envelope helper (LLD 5.1 / 10). Handlers registered in main.py."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error. Carries an RMS-E-* code + HTTP status."""

    code: str = "RMS-E-5000"
    http_status: int = 500

    def __init__(self, message: str, *, code: str | None = None,
                 http_status: int | None = None, details: list[Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or []


class ValidationError(AppError):
    code = "RMS-E-4001"
    http_status = 422


class AuthError(AppError):
    """401 — authentication failures (bad credentials, expired/invalid token)."""
    code = "RMS-E-4011"
    http_status = 401


class ForbiddenError(AppError):
    """403 — role/row-scope not permitted (INV-07)."""
    code = "RMS-E-4031"
    http_status = 403


class NotFoundError(AppError):
    code = "RMS-E-4041"
    http_status = 404


class ConflictError(AppError):
    code = "RMS-E-4091"
    http_status = 409


class TransitionError(AppError):
    """422 — invalid state transition / missing comment (INV-01)."""
    code = "RMS-E-4221"
    http_status = 422


class AgentFailure(AppError):
    code = "RMS-E-5021"
    http_status = 502


class StorageError(AppError):
    code = "RMS-E-5031"
    http_status = 502


def error_body(code: str, message: str, details: list[Any] | None = None) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message, "details": details or []}}
