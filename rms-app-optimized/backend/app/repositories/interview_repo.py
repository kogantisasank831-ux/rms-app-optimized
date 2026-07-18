"""interview_repo — DB access for Interview (no business rules)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview import Interview, InterviewPanelist


async def get_by_id(db: AsyncSession, interview_id: uuid.UUID) -> Interview | None:
    return (
        await db.execute(select(Interview).where(Interview.interview_id == interview_id))
    ).unique().scalar_one_or_none()


async def list_by_application(db: AsyncSession, application_id: uuid.UUID) -> list[Interview]:
    rows = (
        await db.execute(
            select(Interview)
            .where(Interview.application_id == application_id)
            .order_by(Interview.scheduled_start)
        )
    ).unique().scalars().all()
    return list(rows)


async def list_for_panelist(db: AsyncSession, user_id: uuid.UUID) -> list[Interview]:
    rows = (
        await db.execute(
            select(Interview)
            .join(InterviewPanelist, InterviewPanelist.interview_id == Interview.interview_id)
            .where(InterviewPanelist.user_id == user_id)
            .order_by(Interview.scheduled_start)
        )
    ).unique().scalars().all()
    return list(rows)

