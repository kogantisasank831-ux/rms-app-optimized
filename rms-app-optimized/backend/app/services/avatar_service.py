"""avatar_service — profile-photo processing + storage.

One uploaded image becomes two efficient WebP renditions in MinIO under ``avatars/``:

  * icon    — 96x96, quality ~72  → the small avatar shown throughout lists / nav (a few KB,
              loads instantly wherever a person is represented instead of their initials).
  * profile — 384x384, quality ~82 → the larger, still-compressed picture on the profile page.

Each image is EXIF-oriented, converted to RGB, centre-cropped to a square and metadata-stripped
(WebP re-encode drops EXIF). Object keys are deterministic per owner so a re-upload overwrites
in place (no orphaned blobs). All CPU-bound PIL work is offloaded from the event loop.
"""
from __future__ import annotations

import io

from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageOps

from app.core.config import settings
from app.core.errors import ValidationError
from app.services import storage_service

_ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_ICON_PX = 96
_PROFILE_PX = 384
_ICON_QUALITY = 72
_PROFILE_QUALITY = 82


def keys_for(owner_type: str, owner_id) -> tuple[str, str]:
    """Deterministic (icon_key, profile_key) for a person. owner_type: 'users' | 'candidates'."""
    base = f"{storage_service.AVATAR_PREFIX}{owner_type}/{owner_id}"
    return f"{base}/icon.webp", f"{base}/profile.webp"


def _render(data: bytes) -> tuple[bytes, bytes]:
    """Decode the upload and produce (icon_bytes, profile_bytes) as compressed WebP squares."""
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)  # honour phone-camera orientation
        im = im.convert("RGB")
        # ImageOps.fit centre-crops to the exact target square (no distortion).
        icon = ImageOps.fit(im, (_ICON_PX, _ICON_PX), Image.LANCZOS)
        profile = ImageOps.fit(im, (_PROFILE_PX, _PROFILE_PX), Image.LANCZOS)

    ibuf, pbuf = io.BytesIO(), io.BytesIO()
    icon.save(ibuf, format="WEBP", quality=_ICON_QUALITY, method=6)
    profile.save(pbuf, format="WEBP", quality=_PROFILE_QUALITY, method=6)
    return ibuf.getvalue(), pbuf.getvalue()


async def process_and_store(*, owner_type: str, owner_id, data: bytes, content_type: str) -> tuple[str, str]:
    """Validate + render + upload both renditions. Returns (icon_key, profile_key).

    Raises ValidationError on an unsupported / oversized / unreadable image so the caller
    surfaces a friendly message and never persists a half-written photo.
    """
    if (content_type or "").lower() not in _ALLOWED_TYPES:
        raise ValidationError("Photo must be a JPEG, PNG or WebP image", code="RMS-E-4001")
    if not data:
        raise ValidationError("Photo file is empty", code="RMS-E-4001")
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"Photo exceeds {settings.MAX_UPLOAD_MB} MB limit", code="RMS-E-4001")

    try:
        icon_bytes, profile_bytes = await run_in_threadpool(_render, data)
    except ValidationError:
        raise
    except Exception as exc:  # PIL raises a variety of errors on malformed input
        raise ValidationError(
            "Could not read that image — please upload a valid photo.", code="RMS-E-4001"
        ) from exc

    icon_key, profile_key = keys_for(owner_type, owner_id)
    meta = {"entity-type": owner_type.upper().rstrip("S"), "entity-id": str(owner_id)}
    await storage_service.put_object(icon_key, icon_bytes, "image/webp", metadata=meta)
    await storage_service.put_object(profile_key, profile_bytes, "image/webp", metadata=meta)
    return icon_key, profile_key


async def url_for(key: str | None) -> str | None:
    """Presigned GET url for a stored rendition (or None). Skips the existence stat for speed."""
    if not key:
        return None
    return await storage_service.presigned_get_url(key, ensure_exists=False)


async def urls(icon_key: str | None, profile_key: str | None) -> dict:
    """Both photo urls as an attachable dict: {photo_icon_url, photo_url}."""
    return {
        "photo_icon_url": await url_for(icon_key),
        "photo_url": await url_for(profile_key),
    }
