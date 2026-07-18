"""jd_service — AGENT-2 jd_creation orchestration + JD version management (T-203).

Responsibilities:
  * generate:      call the jd_creation agent from the requisition facts, persist as a new
                   agent-authored version, audit. Agent failure never blocks the manual path.
  * save_manual:   persist an HM/HR hand-edited JD as a new (non-agent) version.
  * list_versions: read-scoped version history for the RRF detail JD panel.

Row-scope: HM may only touch JDs of RRFs they own; HR/ADMIN unrestricted (role gate is applied
at the router via require_roles). Read-scope reuses rrf_service.get_rrf (BU_HEAD sees own BU).
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import jd_creation
from app.core.errors import ForbiddenError, NotFoundError
from app.models.jd_version import RrfJdVersion
from app.models.rrf import RRF
from app.models.user import User
from app.repositories import jd_repo, rrf_repo
from app.services import audit_service, rrf_service


def _serialize_version(row: RrfJdVersion) -> dict:
    return {
        "jd_id": str(row.jd_id),
        "version_no": row.version_no,
        "jd_markdown": row.jd_markdown,
        "generated_by_agent": row.generated_by_agent,
        "created_by": str(row.created_by),
        "created_at": row.created_at,
    }


async def _load_writable_rrf(db: AsyncSession, user: User, rrf_id: uuid.UUID) -> RRF:
    rrf = await rrf_repo.get_by_id(db, rrf_id)
    if rrf is None:
        raise NotFoundError("RRF not found", code="RMS-E-4041")
    # HM may only author JDs for their own requisitions (HR/ADMIN unrestricted)
    if user.role_code == "HIRING_MANAGER" and rrf.created_by != user.user_id:
        raise ForbiddenError("Not the owner of this RRF", code="RMS-E-4031")
    return rrf


async def _persist_version(
    db: AsyncSession,
    rrf_id: uuid.UUID,
    jd_markdown: str,
    created_by: uuid.UUID,
    *,
    generated_by_agent: bool,
) -> dict:
    version_no = await jd_repo.next_version_no(db, rrf_id)
    row = RrfJdVersion(
        rrf_id=rrf_id,
        version_no=version_no,
        jd_markdown=jd_markdown,
        generated_by_agent=generated_by_agent,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)  # populate server defaults (jd_id, created_at)
    return _serialize_version(row)


async def generate(db: AsyncSession, user: User, rrf_id: uuid.UUID) -> dict:
    rrf = await _load_writable_rrf(db, user, rrf_id)
    facts = rrf_service.serialize(rrf)

    # agent call logs its own ai_agent_runs row (INV-12) in an independent session;
    # on failure it raises AgentFailure (RMS-E-5021) and the manual save path stays available.
    agent_out = await jd_creation.generate_jd(
        facts, facts["skills"], rrf_id=str(rrf_id), triggered_by=user.user_id
    )

    version = await _persist_version(
        db, rrf_id, agent_out["jd_markdown"], user.user_id, generated_by_agent=True
    )
    await audit_service.record(
        db, entity_type="RRF", entity_id=str(rrf_id), action="JD_GENERATE",
        performed_by=user.user_id,
        after_state={"version_no": version["version_no"], "generated_by_agent": True},
    )
    await db.commit()
    return {
        "version": version,
        "seo_title": agent_out.get("seo_title", ""),
        "keywords": agent_out.get("keywords", []),
    }


async def save_manual(db: AsyncSession, user: User, rrf_id: uuid.UUID, jd_markdown: str) -> dict:
    await _load_writable_rrf(db, user, rrf_id)
    version = await _persist_version(
        db, rrf_id, jd_markdown, user.user_id, generated_by_agent=False
    )
    await audit_service.record(
        db, entity_type="RRF", entity_id=str(rrf_id), action="JD_EDIT",
        performed_by=user.user_id,
        after_state={"version_no": version["version_no"], "generated_by_agent": False},
    )
    await db.commit()
    return version


async def list_versions(db: AsyncSession, user: User, rrf_id: uuid.UUID) -> list[dict]:
    # reuse RRF read-scope (raises NotFound/Forbidden as appropriate, incl. BU_HEAD own-BU rule)
    await rrf_service.get_rrf(db, user, rrf_id)
    rows = await jd_repo.list_for_rrf(db, rrf_id)
    return [_serialize_version(r) for r in rows]
