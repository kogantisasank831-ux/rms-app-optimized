"""/health router — public liveness (DB + MinIO ping)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    checks: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["db"] = f"error: {type(exc).__name__}"

    if settings.MINIO_ENDPOINT and settings.MINIO_BUCKET:
        try:
            from minio import Minio

            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            # bucket_exists is blocking IO — run off the event loop
            exists = await run_in_threadpool(client.bucket_exists, settings.MINIO_BUCKET)
            checks["minio"] = "ok" if exists else "bucket_missing"
        except Exception as exc:  # noqa: BLE001
            checks["minio"] = f"error: {type(exc).__name__}"
    else:
        checks["minio"] = "not_configured"

    healthy = checks.get("db") == "ok"
    return {"success": True, "data": {"status": "ok" if healthy else "degraded", "checks": checks}}
