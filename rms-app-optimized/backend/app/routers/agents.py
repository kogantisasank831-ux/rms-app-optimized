"""/agents router — AI observability: ai_agent_runs viewer (T-402)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_roles
from app.models.user import User
from app.utils import pagination

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/runs")
async def agent_runs(
    agent_name: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles("ADMIN", "HR")),
) -> dict:
    p = pagination.resolve(page, limit)
    where = "WHERE 1=1"
    params: dict = {}
    if agent_name:
        where += " AND agent_name = :an"
        params["an"] = agent_name
    total = (await db.execute(text(f"SELECT count(*) FROM ai_agent_runs {where}"), params)).scalar_one()
    rows = (
        await db.execute(
            text(
                f"SELECT run_id, agent_name, entity_type, entity_id, model, status, "
                f"prompt_tokens, completion_tokens, latency_ms, created_at "
                f"FROM ai_agent_runs {where} ORDER BY created_at DESC LIMIT :lim OFFSET :off"
            ),
            {**params, "lim": p.limit, "off": p.offset},
        )
    ).all()
    items = [
        {"run_id": str(r[0]), "agent_name": r[1], "entity_type": r[2], "entity_id": r[3],
         "model": r[4], "status": r[5], "prompt_tokens": r[6], "completion_tokens": r[7],
         "latency_ms": r[8], "created_at": r[9].isoformat()}
        for r in rows
    ]
    return {"success": True, "data": items, "meta": pagination.meta(p, total)}
