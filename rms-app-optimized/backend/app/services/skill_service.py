"""skill_service — Skill Master xlsx import (INV-09) + typeahead search."""
from __future__ import annotations

import io
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.skill import SkillMaster
from app.repositories import skill_repo
from app.services import audit_service
from app.utils import pagination


def _parse_xlsx(data: bytes) -> list[tuple[str, str | None, list[str]]]:
    """Parse an .xlsx with columns skill_name, [skill_category], [aliases].
    aliases may be a JSON array or a comma-separated string."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError("Could not read xlsx file", code="RMS-E-4001") from exc

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValidationError("Empty spreadsheet", code="RMS-E-4001")

    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    if "skill_name" not in idx:
        raise ValidationError("Missing required column 'skill_name'", code="RMS-E-4001")

    out: list[tuple[str, str | None, list[str]]] = []
    for r in rows[1:]:
        name = r[idx["skill_name"]] if idx["skill_name"] < len(r) else None
        if not name:
            continue
        cat = None
        if "skill_category" in idx and idx["skill_category"] < len(r):
            cat = r[idx["skill_category"]]
        raw_alias = None
        if "aliases" in idx and idx["aliases"] < len(r):
            raw_alias = r[idx["aliases"]]
        aliases: list[str] = []
        if raw_alias:
            s = str(raw_alias).strip()
            if s.startswith("["):
                try:
                    aliases = list(json.loads(s))
                except json.JSONDecodeError:
                    aliases = [s]
            else:
                aliases = [a.strip() for a in s.split(",") if a.strip()]
        out.append((str(name).strip(), str(cat).strip() if cat else None, aliases))
    return out


async def import_xlsx(db: AsyncSession, data: bytes, actor_id) -> dict:
    parsed = _parse_xlsx(data)
    inserted = updated = 0
    for name, cat, aliases in parsed:
        result = await skill_repo.upsert(db, name, cat, aliases)
        if result == "inserted":
            inserted += 1
        else:
            updated += 1
    await audit_service.record(
        db, entity_type="SKILL", entity_id="skill_master", action="IMPORT",
        performed_by=actor_id,
        after_state={"rows": len(parsed), "inserted": inserted, "updated": updated},
    )
    await db.commit()
    return {"rows": len(parsed), "inserted": inserted, "updated": updated}


def _clean(skill_name: str, category: str | None, aliases: list[str] | None) -> tuple[str, str | None, list[str]]:
    name = (skill_name or "").strip()
    if not name:
        raise ValidationError("skill_name is required", code="RMS-E-4001")
    cat = category.strip() if category and category.strip() else None
    clean_aliases = [a.strip() for a in (aliases or []) if a and a.strip()]
    return name, cat, clean_aliases


async def create_skill(
    db: AsyncSession, skill_name: str, category: str | None, aliases: list[str] | None, actor_id
) -> dict:
    name, cat, clean_aliases = _clean(skill_name, category, aliases)
    if await skill_repo.get_by_name(db, name):
        raise ConflictError(f"Skill '{name}' already exists", code="RMS-E-4091")
    row = await skill_repo.insert(db, name, cat, clean_aliases)
    await audit_service.record(
        db, entity_type="SKILL", entity_id=str(row.skill_id), action="CREATE",
        performed_by=actor_id, after_state=_public(row),
    )
    await db.commit()
    await db.refresh(row)
    return _public(row)


async def update_skill(
    db: AsyncSession, skill_id: int, skill_name: str, category: str | None, aliases: list[str] | None, actor_id
) -> dict:
    row = await skill_repo.get_by_id(db, skill_id)
    if not row:
        raise NotFoundError(f"Skill {skill_id} not found", code="RMS-E-4041")
    name, cat, clean_aliases = _clean(skill_name, category, aliases)
    clash = await skill_repo.get_by_name(db, name)
    if clash and clash.skill_id != skill_id:
        raise ConflictError(f"Skill '{name}' already exists", code="RMS-E-4091")
    before = _public(row)
    row = await skill_repo.update(db, row, skill_name=name, category=cat, aliases=clean_aliases)
    await audit_service.record(
        db, entity_type="SKILL", entity_id=str(row.skill_id), action="UPDATE",
        performed_by=actor_id, before_state=before, after_state=_public(row),
    )
    await db.commit()
    await db.refresh(row)
    return _public(row)


async def list_skills(db: AsyncSession, q: str | None, page: int, limit: int) -> tuple[list[dict], dict]:
    p = pagination.resolve(page, limit)
    rows, total = await skill_repo.search(db, q, p.limit, p.offset)
    return [_public(s) for s in rows], pagination.meta(p, total)


def _public(s: SkillMaster) -> dict:
    return {
        "skill_id": s.skill_id,
        "skill_name": s.skill_name,
        "skill_category": s.skill_category,
        "aliases": s.aliases,
    }
