"""/rrfs router — RRF CRUD (create DRAFT, role-scoped read, edit while DRAFT/REJECTED),
state transitions (T-202), and JD versions via the jd_creation agent (T-203).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_roles
from app.models.user import User
from app.schemas.jd import JdManualSave
from app.schemas.rrf import RrfCreate, RrfUpdate, TransitionRequest
from app.services import jd_service, rrf_service

router = APIRouter(prefix="/rrfs", tags=["rrfs"])

_READ_ROLES = ("ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD")
_WRITE_ROLES = ("ADMIN", "HIRING_MANAGER")
# JD authoring: HM (own RRF), HR, ADMIN (LLD 6.3 trigger). BU_HEAD is read-only on JDs.
_JD_WRITE_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")
# any RRF-facing role may attempt a transition; the guard table enforces per-action roles
_TRANSITION_ROLES = ("ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD")
# candidate matching touches candidate data -> BU_HEAD excluded (INV-07)
_MATCH_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rrf(
    payload: RrfCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> dict:
    data = await rrf_service.create_rrf(db, user, payload)
    return {"success": True, "data": data}


@router.get("")
async def list_rrfs(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    items, meta = await rrf_service.list_rrfs(db, user, status=status_filter, page=page, limit=limit)
    return {"success": True, "data": items, "meta": meta}


@router.get("/{rrf_id}")
async def get_rrf(
    rrf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    data = await rrf_service.get_rrf(db, user, rrf_id)
    return {"success": True, "data": data}


@router.patch("/{rrf_id}")
async def update_rrf(
    rrf_id: uuid.UUID,
    payload: RrfUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> dict:
    data = await rrf_service.update_rrf(db, user, rrf_id, payload)
    return {"success": True, "data": data}


@router.post("/{rrf_id}/transition")
async def transition_rrf(
    rrf_id: uuid.UUID,
    payload: TransitionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_TRANSITION_ROLES)),
) -> dict:
    data = await rrf_service.transition(db, user, rrf_id, payload.action, payload.comment)
    return {"success": True, "data": data}


# --------------------------------------------------------------------- JD versions (T-203)
@router.post("/{rrf_id}/jd/generate")
async def generate_jd(
    rrf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_JD_WRITE_ROLES)),
) -> dict:
    """AGENT-2 jd_creation → persist a new agent-authored JD version (LLD 6.3)."""
    data = await jd_service.generate(db, user, rrf_id)
    return {"success": True, "data": data}


@router.get("/{rrf_id}/jd")
async def list_jd(
    rrf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    data = await jd_service.list_versions(db, user, rrf_id)
    return {"success": True, "data": data}


@router.post("/{rrf_id}/jd")
async def save_jd(
    rrf_id: uuid.UUID,
    payload: JdManualSave,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_JD_WRITE_ROLES)),
) -> dict:
    """Persist an HM/HR hand-edited JD as a new (non-agent) version — editable before submit."""
    data = await jd_service.save_manual(db, user, rrf_id, payload.jd_markdown)
    return {"success": True, "data": data}


# --------------------------------------------------------------------- candidate matching (T-305)
@router.get("/{rrf_id}/match-candidates")
async def match_candidates(
    rrf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_MATCH_ROLES)),
) -> dict:
    """AGENT-3 candidate_matching → advisory ranking of the active pool (LLD 6.4)."""
    data = await rrf_service.match_candidates(db, user, rrf_id)
    return {"success": True, "data": data}
