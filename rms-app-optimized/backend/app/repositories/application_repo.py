"""application_repo — DB access for Application (no business rules)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.rrf import RRF


async def get_by_id(db: AsyncSession, application_id: uuid.UUID) -> Application | None:
    return (
        await db.execute(select(Application).where(Application.application_id == application_id))
    ).unique().scalar_one_or_none()


async def lock_by_id(db: AsyncSession, application_id: uuid.UUID) -> bool:
    """Lock one application row for the current transaction.

    Pipeline transitions are user-driven and can be triggered by multiple hiring users at once.
    Locking the row prevents two requests from both validating the same old stage and writing
    contradictory history entries. Select only the primary key so eager relationships are not
    included in the FOR UPDATE clause.
    """
    row = await db.execute(
        select(Application.application_id)
        .where(Application.application_id == application_id)
        .with_for_update(of=Application)
    )
    return row.scalar_one_or_none() is not None


async def get_by_rrf_candidate(
    db: AsyncSession, rrf_id: uuid.UUID, candidate_id: uuid.UUID
) -> Application | None:
    return (
        await db.execute(
            select(Application).where(
                Application.rrf_id == rrf_id, Application.candidate_id == candidate_id
            )
        )
    ).unique().scalar_one_or_none()


async def list_scoped(
    db: AsyncSession,
    *,
    rrf_id: uuid.UUID | None = None,
    stage: str | None = None,
    status: str | None = None,
    hm_user_id: uuid.UUID | None = None,
    q: str | None = None,
    sort: str = "recent",
    limit: int,
    offset: int,
) -> tuple[list[Application], int]:
    stmt = select(Application)
    if rrf_id is not None:
        stmt = stmt.where(Application.rrf_id == rrf_id)
    if stage is not None:
        stmt = stmt.where(Application.current_stage == stage)
    if status is not None:
        stmt = stmt.where(Application.status == status)
    if hm_user_id is not None:
        # HM sees only applications on their own RRFs
        stmt = stmt.where(Application.rrf_id.in_(select(RRF.rrf_id).where(RRF.created_by == hm_user_id)))
    if q:
        # search by candidate name (EXISTS subquery — no join needed)
        stmt = stmt.where(Application.candidate.has(Candidate.full_name.ilike(f"%{q.strip()}%")))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    if sort == "score":
        stmt = stmt.order_by(Application.ai_screen_score.desc().nullslast(), Application.created_at.desc())
    elif sort == "name":
        stmt = stmt.join(Candidate, Application.candidate_id == Candidate.candidate_id).order_by(Candidate.full_name.asc())
    else:  # recent
        stmt = stmt.order_by(Application.created_at.desc())

    rows = (await db.execute(stmt.limit(limit).offset(offset))).unique().scalars().all()
    return list(rows), total

