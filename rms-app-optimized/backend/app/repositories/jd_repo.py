"""jd_repo — DB access for rrf_jd_versions (no business rules)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jd_version import RrfJdVersion


async def next_version_no(db: AsyncSession, rrf_id: uuid.UUID) -> int:
    """1-based, monotonic per RRF (matches UNIQUE (rrf_id, version_no))."""
    current = (
        await db.execute(
            select(func.coalesce(func.max(RrfJdVersion.version_no), 0)).where(
                RrfJdVersion.rrf_id == rrf_id
            )
        )
    ).scalar_one()
    return int(current) + 1


async def list_for_rrf(db: AsyncSession, rrf_id: uuid.UUID) -> list[RrfJdVersion]:
    rows = (
        await db.execute(
            select(RrfJdVersion)
            .where(RrfJdVersion.rrf_id == rrf_id)
            .order_by(RrfJdVersion.version_no.desc())
        )
    ).scalars().all()
    return list(rows)
