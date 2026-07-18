"""storage_service — MinIO access (single provided bucket, key prefixes per ADR-003).

Uploads are server-side only (never presigned PUT from browser). Downloads use short-lived
presigned GET urls. All blocking MinIO calls are offloaded from the event loop.
"""
from __future__ import annotations

import io
from datetime import timedelta

from fastapi.concurrency import run_in_threadpool
from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.errors import NotFoundError, StorageError

# allowed logical prefixes inside the single bucket
CV_PREFIX = "cvs/"
OFFER_PREFIX = "offers/"
TEMPLATE_PREFIX = "templates/"
AVATAR_PREFIX = "avatars/"  # profile photos (icon + profile WebP renditions)
ALLOWED_PREFIXES = (CV_PREFIX, OFFER_PREFIX, TEMPLATE_PREFIX, AVATAR_PREFIX)

_PRESIGN_EXPIRY = timedelta(minutes=15)

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        if not settings.MINIO_ENDPOINT or not settings.MINIO_BUCKET:
            raise StorageError("MinIO is not configured")
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def is_allowed_key(object_key: str) -> bool:
    return object_key.startswith(ALLOWED_PREFIXES)


async def put_object(object_key: str, data: bytes, content_type: str,
                     metadata: dict[str, str] | None = None) -> str:
    """Upload bytes to the bucket; returns the object key. Raises StorageError on failure."""
    client = _get_client()
    try:
        await run_in_threadpool(
            client.put_object,
            settings.MINIO_BUCKET,
            object_key,
            io.BytesIO(data),
            len(data),
            content_type,
            metadata,
        )
    except S3Error as exc:
        raise StorageError(f"Upload failed: {exc.code}") from exc
    return object_key


async def get_object(object_key: str) -> bytes:
    """Fetch an object's bytes (e.g. the fixed offer template). Raises StorageError on failure."""
    client = _get_client()

    def _read() -> bytes:
        resp = client.get_object(settings.MINIO_BUCKET, object_key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    try:
        return await run_in_threadpool(_read)
    except S3Error as exc:
        raise StorageError(f"Read failed: {exc.code}") from exc


async def object_exists(object_key: str) -> bool:
    client = _get_client()
    try:
        await run_in_threadpool(client.stat_object, settings.MINIO_BUCKET, object_key)
        return True
    except S3Error as exc:
        if exc.code in ("NoSuchKey", "NoSuchObject", "NotFound"):
            return False
        raise StorageError(f"Stat failed: {exc.code}") from exc


async def presigned_get_url(object_key: str, *, ensure_exists: bool = True) -> str:
    """Return a presigned GET url (15m). 404 if the object is missing."""
    client = _get_client()
    if ensure_exists and not await object_exists(object_key):
        raise NotFoundError(f"Object not found: {object_key}")
    try:
        return await run_in_threadpool(
            client.presigned_get_object,
            settings.MINIO_BUCKET,
            object_key,
            _PRESIGN_EXPIRY,
        )
    except S3Error as exc:
        raise StorageError(f"Presign failed: {exc.code}") from exc
