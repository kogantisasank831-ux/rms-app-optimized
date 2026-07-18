"""/dashboard router — metrics (role-scoped) + audit-log viewer (T-401/T-402)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_roles
from app.models.user import User
from app.services import dashboard_service
from app.utils import pagination

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/metrics")
async def dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD")),
) -> dict:
    data = await dashboard_service.get_metrics(db, user)
    return {"success": True, "data": data}


@router.get("/dashboard/insights")
async def dashboard_insights(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD")),
) -> dict:
    """AI observability tiles — loaded separately so the core dashboard renders first."""
    data = await dashboard_service.get_insights(db, user)
    return {"success": True, "data": data}


@router.get("/audit")
async def audit_log(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles("ADMIN", "HR")),
) -> dict:
    p = pagination.resolve(page, limit)
    where = "WHERE 1=1"
    params: dict = {}
    if entity_type:
        where += " AND entity_type = :et"
        params["et"] = entity_type
    if entity_id:
        where += " AND entity_id = :eid"
        params["eid"] = entity_id
    total = (await db.execute(text(f"SELECT count(*) FROM audit_logs {where}"), params)).scalar_one()
    rows = (
        await db.execute(
            text(
                f"SELECT audit_id, entity_type, entity_id, action, performed_by, after_state, created_at "
                f"FROM audit_logs {where} ORDER BY created_at DESC LIMIT :lim OFFSET :off"
            ),
            {**params, "lim": p.limit, "off": p.offset},
        )
    ).all()
    items = [
        {"audit_id": r[0], "entity_type": r[1], "entity_id": r[2], "action": r[3],
         "performed_by": str(r[4]) if r[4] else None, "after_state": r[5], "created_at": r[6].isoformat()}
        for r in rows
    ]
    return {"success": True, "data": items, "meta": pagination.meta(p, total)}
