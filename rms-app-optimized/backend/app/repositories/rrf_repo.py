"""rrf_repo — DB access for RRF (no business rules)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rrf import RRF


async def next_rrf_code(db: AsyncSession, year: int) -> str:
    """Next sequential code for the year: RRF-<year>-0001. (Demo-grade; low concurrency.)"""
    row = await db.execute(
        text(
            "SELECT COALESCE(MAX(CAST(split_part(rrf_code, '-', 3) AS int)), 0) "
            "FROM rrf WHERE rrf_code LIKE :p"
        ),
        {"p": f"RRF-{year}-%"},
    )
    nxt = int(row.scalar_one()) + 1
    return f"RRF-{year}-{nxt:04d}"


async def next_job_code(db: AsyncSession, year: int) -> str:
    """Next sequential PUBLIC job id for the year: JOB-<year>-0001. Shown on the careers portal
    (the internal rrf_code is never exposed publicly)."""
    row = await db.execute(
        text(
            "SELECT COALESCE(MAX(CAST(split_part(job_code, '-', 3) AS int)), 0) "
            "FROM rrf WHERE job_code LIKE :p"
        ),
        {"p": f"JOB-{year}-%"},
    )
    nxt = int(row.scalar_one()) + 1
    return f"JOB-{year}-{nxt:04d}"


async def get_by_id(db: AsyncSession, rrf_id: uuid.UUID) -> RRF | None:
    return (
        await db.execute(select(RRF).where(RRF.rrf_id == rrf_id))
    ).unique().scalar_one_or_none()


async def bu_ids_for_head(db: AsyncSession, user_id: uuid.UUID) -> list[int]:
    rows = await db.execute(
        text("SELECT bu_id FROM business_units WHERE bu_head_user_id = :u"), {"u": str(user_id)}
    )
    return [r[0] for r in rows.fetchall()]


async def list_scoped(
    db: AsyncSession,
    *,
    created_by: uuid.UUID | None = None,
    bu_ids: list[int] | None = None,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[RRF], int]:
    stmt = select(RRF)
    if created_by is not None:
        stmt = stmt.where(RRF.created_by == created_by)
    if bu_ids is not None:
        # empty list => no access => no rows
        stmt = stmt.where(RRF.bu_id.in_(bu_ids or [-1]))
    if status is not None:
        stmt = stmt.where(RRF.status == status)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(stmt.order_by(RRF.created_at.desc()).limit(limit).offset(offset))
    ).unique().scalars().all()
    return list(rows), total
