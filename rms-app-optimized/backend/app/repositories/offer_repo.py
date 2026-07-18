"""offer_repo — DB access for Offer (no business rules)."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.offer import Offer


async def next_offer_code(db: AsyncSession, year: int) -> str:
    row = await db.execute(
        text(
            "SELECT COALESCE(MAX(CAST(split_part(offer_code, '-', 3) AS int)), 0) "
            "FROM offers WHERE offer_code LIKE :p"
        ),
        {"p": f"OFR-{year}-%"},
    )
    return f"OFR-{year}-{int(row.scalar_one()) + 1:04d}"


async def get_by_id(db: AsyncSession, offer_id: uuid.UUID) -> Offer | None:
    return (
        await db.execute(select(Offer).where(Offer.offer_id == offer_id))
    ).scalar_one_or_none()


async def get_by_application(db: AsyncSession, application_id: uuid.UUID) -> Offer | None:
    return (
        await db.execute(select(Offer).where(Offer.application_id == application_id))
    ).scalar_one_or_none()


async def list_all(db: AsyncSession) -> list[Offer]:
    return list((await db.execute(select(Offer))).scalars().all())

