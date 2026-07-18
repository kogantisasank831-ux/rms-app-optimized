"""/applications router — link candidate<->RRF, role-scoped read, pipeline transitions (G6-G14)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_roles
from app.models.user import User
from app.schemas.application import ApplicationCreate, TransitionRequest
from app.services import pipeline_service

router = APIRouter(prefix="/applications", tags=["applications"])

_READ_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")
_WRITE_ROLES = ("ADMIN", "HR")
_TRANSITION_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")  # BU_HEAD excluded (INV-07)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> dict:
    data = await pipeline_service.create_application(db, user, payload.rrf_id, payload.candidate_id)
    return {"success": True, "data": data}


@router.get("")
async def list_applications(
    rrf_id: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    sort: str = Query(default="recent"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    items, meta = await pipeline_service.list_applications(
        db, user, rrf_id=rrf_id, stage=stage, status=status_filter,
        q=q, sort=sort, page=page, limit=limit,
    )
    return {"success": True, "data": items, "meta": meta}


@router.get("/pipeline-stats")
async def pipeline_stats(
    rrf_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    return {"success": True, "data": await pipeline_service.pipeline_stats(db, user, rrf_id)}


@router.get("/{application_id}")
async def get_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    data = await pipeline_service.get_application(db, user, application_id)
    return {"success": True, "data": data}


@router.get("/{application_id}/history")
async def application_history(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    data = await pipeline_service.get_history(db, user, application_id)
    return {"success": True, "data": data}


@router.post("/{application_id}/screen")
async def screen_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> dict:
    data = await pipeline_service.screen_application(db, user, application_id)
    return {"success": True, "data": data}


@router.post("/{application_id}/transition")
async def transition_application(
    application_id: uuid.UUID,
    payload: TransitionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_TRANSITION_ROLES)),
) -> dict:
    data = await pipeline_service.transition(
        db, user, application_id, payload.action, payload.comment, payload.target_stage
    )
    return {"success": True, "data": data}
