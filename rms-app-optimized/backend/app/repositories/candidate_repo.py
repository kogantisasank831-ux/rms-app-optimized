"""candidate_repo — DB access for Candidate (no business rules)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate


async def get_by_id(db: AsyncSession, candidate_id: uuid.UUID) -> Candidate | None:
    return (
        await db.execute(select(Candidate).where(Candidate.candidate_id == candidate_id))
    ).scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> Candidate | None:
    return (
        await db.execute(select(Candidate).where(func.lower(Candidate.email) == func.lower(email)))
    ).scalar_one_or_none()


async def get_by_phone(db: AsyncSession, phone_digits: str) -> Candidate | None:
    """Match on digits only, so formatting differences (+91, spaces) don't defeat the check."""
    stmt = select(Candidate).where(
        func.regexp_replace(Candidate.phone, r"\D", "", "g") == phone_digits
    )
    return (await db.execute(stmt)).scalars().first()


async def set_photo(db: AsyncSession, candidate: Candidate, icon_key: str, profile_key: str) -> Candidate:
    candidate.photo_icon_key = icon_key
    candidate.photo_object_key = profile_key
    await db.flush()
    return candidate


async def list_scoped(
    db: AsyncSession, *, hm_user_id: uuid.UUID | None, limit: int, offset: int
) -> tuple[list[Candidate], int]:
    stmt = select(Candidate)
    if hm_user_id is not None:
        # HM sees only candidates that applied to one of their RRFs (via applications)
        rows = await db.execute(
            text(
                "SELECT DISTINCT a.candidate_id FROM applications a "
                "JOIN rrf r ON r.rrf_id = a.rrf_id WHERE r.created_by = :hm"
            ),
            {"hm": str(hm_user_id)},
        )
        ids = [r[0] for r in rows.fetchall()]
        if not ids:
            return [], 0
        stmt = stmt.where(Candidate.candidate_id.in_(ids))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = (
        await db.execute(stmt.order_by(Candidate.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(result), total
