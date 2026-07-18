"""skill_repo — DB access for SkillMaster (no business rules)."""
from __future__ import annotations

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import SkillMaster


async def search(db: AsyncSession, q: str | None, limit: int, offset: int) -> tuple[list[SkillMaster], int]:
    """Case-insensitive match on skill_name or any alias; active skills only. Returns (rows, total)."""
    base = select(SkillMaster).where(SkillMaster.is_active.is_(True))
    if q:
        like = f"%{q.lower()}%"
        # name match OR alias-array contains a matching entry (jsonb)
        alias_match = text(
            "EXISTS (SELECT 1 FROM jsonb_array_elements_text(skill_master.aliases) a "
            "WHERE lower(a) LIKE :like)"
        ).bindparams(like=like)
        base = base.where(or_(func.lower(SkillMaster.skill_name).like(like), alias_match))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(SkillMaster.skill_name).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total


async def get_by_id(db: AsyncSession, skill_id: int) -> SkillMaster | None:
    return (
        await db.execute(select(SkillMaster).where(SkillMaster.skill_id == skill_id))
    ).scalar_one_or_none()


async def get_by_name(db: AsyncSession, skill_name: str) -> SkillMaster | None:
    return (
        await db.execute(
            select(SkillMaster).where(func.lower(SkillMaster.skill_name) == skill_name.lower())
        )
    ).scalar_one_or_none()


async def insert(db: AsyncSession, skill_name: str, category: str | None, aliases: list[str]) -> SkillMaster:
    """Insert a new skill row and return it. Caller must guard for name conflicts."""
    row = SkillMaster(skill_name=skill_name, skill_category=category, aliases=aliases, is_active=True)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def update(
    db: AsyncSession, row: SkillMaster, *, skill_name: str, category: str | None, aliases: list[str]
) -> SkillMaster:
    row.skill_name = skill_name
    row.skill_category = category
    row.aliases = aliases
    await db.flush()
    return row


async def upsert(db: AsyncSession, skill_name: str, category: str | None, aliases: list[str]) -> str:
    """Insert or update a skill by name. Returns 'inserted' | 'updated'."""
    import json

    res = await db.execute(
        text(
            "INSERT INTO skill_master (skill_name, skill_category, aliases) "
            "VALUES (:n, :c, CAST(:a AS jsonb)) "
            "ON CONFLICT (skill_name) DO UPDATE SET "
            "skill_category = EXCLUDED.skill_category, aliases = EXCLUDED.aliases, is_active = TRUE "
            "RETURNING (xmax = 0) AS inserted"
        ),
        {"n": skill_name, "c": category, "a": json.dumps(aliases)},
    )
    inserted = res.scalar_one()
    return "inserted" if inserted else "updated"
