"""Restricted administrative access to shared storage templates.

Candidate CVs, offer letters, and profile images are intentionally *not* exposed through a
key-based generic endpoint. Their owning entity services perform the required role and row-scope
checks before returning a short-lived URL.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import require_roles
from app.core.errors import ValidationError
from app.models.user import User
from app.services import storage_service

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/presign")
async def presign(
    object_key: str = Query(..., min_length=1),
    _user: User = Depends(require_roles("ADMIN")),
) -> dict:
    """Presign a shared template for administrators.

    Private candidate/offer/avatar objects must be downloaded through their entity endpoints;
    accepting those raw keys here would let any authenticated user bypass ownership checks.
    """
    if not object_key.startswith(storage_service.TEMPLATE_PREFIX):
        raise ValidationError(
            "The generic presign endpoint only accepts keys under templates/",
            code="RMS-E-4001",
        )
    url = await storage_service.presigned_get_url(object_key)
    return {
        "success": True,
        "data": {"object_key": object_key, "download_url": url, "expires_in": 900},
    }
