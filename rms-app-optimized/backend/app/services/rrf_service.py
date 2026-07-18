"""rrf_service — RRF create/read/update, validation, access scoping, audit.

State transitions (submit/approve/hold/cancel) are handled separately in T-202.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError, TransitionError, ValidationError
from app.models.business_unit import BusinessUnit
from app.models.rrf import RRF, RrfSkill
from app.models.skill import SkillMaster
from app.models.user import User
from app.agents import candidate_matching
from app.repositories import rrf_repo
from app.services import audit_service, notification_service
from app.utils import pagination

_EDITABLE_STATUSES = {"DRAFT", "REJECTED"}


# --------------------------------------------------------------------------- helpers
async def _validate_bu(db: AsyncSession, bu_id: int) -> None:
    if await db.get(BusinessUnit, bu_id) is None:
        raise ValidationError(f"business_unit {bu_id} not found", code="RMS-E-4001")


async def _validate_skills(db: AsyncSession, skills) -> None:
    if not skills:
        return
    ids = {s.skill_id for s in skills}
    found = (
        await db.execute(select(func.count()).select_from(
            select(SkillMaster.skill_id).where(SkillMaster.skill_id.in_(ids)).subquery()
        ))
    ).scalar_one()
    if found != len(ids):
        raise ValidationError("one or more skill_id not found in skill_master", code="RMS-E-4001")


def _parse_uuid(value: str | None, field: str) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(f"invalid uuid for {field}", code="RMS-E-4001") from exc


async def _assert_can_read(db: AsyncSession, user: User, rrf: RRF) -> None:
    role = user.role_code
    if role in ("ADMIN", "HR"):
        return
    if role == "HIRING_MANAGER" and rrf.created_by == user.user_id:
        return
    if role == "BU_HEAD" and rrf.bu_id in await rrf_repo.bu_ids_for_head(db, user.user_id):
        return
    raise ForbiddenError("Not permitted to access this RRF", code="RMS-E-4031")


def serialize(rrf: RRF) -> dict:
    return {
        "rrf_id": str(rrf.rrf_id),
        "rrf_code": rrf.rrf_code,
        "job_code": rrf.job_code,
        "position_title": rrf.position_title,
        "positions_count": rrf.positions_count,
        "status": rrf.status,
        "project_name": rrf.project_name,
        "bu_id": rrf.bu_id,
        "bu_name": rrf.business_unit.bu_name if rrf.business_unit else None,
        "needed_by_date": rrf.needed_by_date,
        "created_at": rrf.created_at,
        "assignment_location": rrf.assignment_location,
        "base_location": rrf.base_location,
        "justification": rrf.justification,
        "project_type": rrf.project_type,
        "salary_range": rrf.salary_range,
        "wfh_allowed": rrf.wfh_allowed,
        "shift_hours": rrf.shift_hours,
        "reporting_to": rrf.reporting_to,
        "scope_of_work": rrf.scope_of_work,
        "responsibilities": rrf.responsibilities,
        "education_qualification": rrf.education_qualification,
        "min_experience_years": float(rrf.min_experience_years),
        "created_by": str(rrf.created_by),
        "hr_rep_user_id": str(rrf.hr_rep_user_id) if rrf.hr_rep_user_id else None,
        "approved_by": str(rrf.approved_by) if rrf.approved_by else None,
        "positions_filled": rrf.positions_filled,
        "skills": [
            {"skill_id": s.skill_id, "skill_name": s.skill.skill_name,
             "req_type": s.req_type, "priority": s.priority}
            for s in rrf.skills
        ],
    }


# --------------------------------------------------------------------------- operations
async def create_rrf(db: AsyncSession, user: User, payload) -> dict:
    await _validate_bu(db, payload.bu_id)
    await _validate_skills(db, payload.skills)
    hr_rep = _parse_uuid(payload.hr_rep_user_id, "hr_rep_user_id")

    year = datetime.datetime.now(datetime.timezone.utc).year
    code = await rrf_repo.next_rrf_code(db, year)
    job_code = await rrf_repo.next_job_code(db, year)

    rrf = RRF(
        rrf_code=code,
        job_code=job_code,
        position_title=payload.position_title,
        positions_count=payload.positions_count,
        assignment_location=payload.assignment_location,
        base_location=payload.base_location,
        justification=payload.justification,
        project_name=payload.project_name,
        project_type=payload.project_type,
        needed_by_date=payload.needed_by_date,
        salary_range=payload.salary_range,
        wfh_allowed=payload.wfh_allowed,
        shift_hours=payload.shift_hours,
        reporting_to=payload.reporting_to,
        scope_of_work=payload.scope_of_work,
        responsibilities=payload.responsibilities,
        education_qualification=payload.education_qualification,
        min_experience_years=payload.min_experience_years,
        bu_id=payload.bu_id,
        status="DRAFT",
        created_by=user.user_id,
        hr_rep_user_id=hr_rep,
    )
    for s in payload.skills:
        rrf.skills.append(RrfSkill(skill_id=s.skill_id, req_type=s.req_type, priority=s.priority))

    db.add(rrf)
    await db.flush()
    await audit_service.record(
        db, entity_type="RRF", entity_id=str(rrf.rrf_id), action="CREATE",
        performed_by=user.user_id,
        after_state={"rrf_code": code, "status": "DRAFT", "position_title": rrf.position_title},
    )
    await db.commit()
    return {"rrf_id": str(rrf.rrf_id), "rrf_code": code, "status": "DRAFT"}


async def get_rrf(db: AsyncSession, user: User, rrf_id: uuid.UUID) -> dict:
    rrf = await rrf_repo.get_by_id(db, rrf_id)
    if rrf is None:
        raise NotFoundError("RRF not found", code="RMS-E-4041")
    await _assert_can_read(db, user, rrf)
    return serialize(rrf)


async def list_rrfs(
    db: AsyncSession, user: User, *, status: str | None, page: int, limit: int
) -> tuple[list[dict], dict]:
    p = pagination.resolve(page, limit)
    role = user.role_code
    created_by = None
    bu_ids = None
    if role == "HIRING_MANAGER":
        created_by = user.user_id
    elif role == "BU_HEAD":
        bu_ids = await rrf_repo.bu_ids_for_head(db, user.user_id)
    # HR / ADMIN: unrestricted
    rows, total = await rrf_repo.list_scoped(
        db, created_by=created_by, bu_ids=bu_ids, status=status, limit=p.limit, offset=p.offset
    )
    items = [
        {
            "rrf_id": str(r.rrf_id), "rrf_code": r.rrf_code, "position_title": r.position_title,
            "positions_count": r.positions_count, "status": r.status, "project_name": r.project_name,
            "bu_id": r.bu_id, "bu_name": r.business_unit.bu_name if r.business_unit else None,
            "needed_by_date": r.needed_by_date, "created_at": r.created_at,
        }
        for r in rows
    ]
    return items, pagination.meta(p, total)


async def update_rrf(db: AsyncSession, user: User, rrf_id: uuid.UUID, payload) -> dict:
    rrf = await rrf_repo.get_by_id(db, rrf_id)
    if rrf is None:
        raise NotFoundError("RRF not found", code="RMS-E-4041")

    # HM may edit only own RRFs in DRAFT/REJECTED; ADMIN may edit any
    if user.role_code == "HIRING_MANAGER":
        if rrf.created_by != user.user_id:
            raise ForbiddenError("Not the owner of this RRF", code="RMS-E-4031")
        if rrf.status not in _EDITABLE_STATUSES:
            raise ValidationError(
                f"RRF in status {rrf.status} is not editable", code="RMS-E-4001"
            )

    data = payload.model_dump(exclude_unset=True)
    skills = data.pop("skills", None)
    if "hr_rep_user_id" in data:
        data["hr_rep_user_id"] = _parse_uuid(data["hr_rep_user_id"], "hr_rep_user_id")
    for key, value in data.items():
        setattr(rrf, key, value)

    if skills is not None:
        await _validate_skills(db, payload.skills)
        rrf.skills.clear()
        for s in payload.skills:
            rrf.skills.append(RrfSkill(skill_id=s.skill_id, req_type=s.req_type, priority=s.priority))

    rrf.updated_at = func.now()
    await audit_service.record(
        db, entity_type="RRF", entity_id=str(rrf.rrf_id), action="UPDATE",
        performed_by=user.user_id, after_state={"fields": list(data.keys())},
    )
    await db.commit()

    refreshed = await rrf_repo.get_by_id(db, rrf_id)
    return serialize(refreshed)


# =========================================================================== #
# STATE MACHINE (G1-G5) — single data-driven guard table (LLD 4.1 / 4.4)      #
# =========================================================================== #
async def _guard_submit(rrf: RRF) -> None:
    # G1: at least one ESSENTIAL skill required before submission
    if not any(s.req_type == "ESSENTIAL" for s in rrf.skills):
        raise TransitionError(
            "RRF requires at least one ESSENTIAL skill before submission", code="RMS-E-4221"
        )


# action -> rule. `to` may be None when the target is computed dynamically (RESUME).
RRF_GUARD: dict[str, dict] = {
    "SUBMIT": {"from": {"DRAFT", "REJECTED"}, "to": "PENDING_APPROVAL",
               "roles": {"HIRING_MANAGER", "ADMIN"}, "guard": _guard_submit,
               "notify": ["bu_head"]},
    "APPROVE": {"from": {"PENDING_APPROVAL"}, "to": "APPROVED",
                "roles": {"BU_HEAD", "ADMIN"}, "notify": ["creator", "hr_rep"]},
    "REJECT": {"from": {"PENDING_APPROVAL"}, "to": "REJECTED",
               "roles": {"BU_HEAD", "ADMIN"}, "notify": ["creator"]},
    "REQUEST_CANCEL": {"from": {"APPROVED"}, "to": "CANCEL_REQUESTED",
                       "roles": {"HIRING_MANAGER", "ADMIN"}, "notify": ["bu_head"]},   # INV-08
    "CONFIRM_CANCEL": {"from": {"CANCEL_REQUESTED"}, "to": "CANCELLED",
                       "roles": {"BU_HEAD", "ADMIN"}, "notify": ["creator"]},           # INV-08
    "DECLINE_CANCEL": {"from": {"CANCEL_REQUESTED"}, "to": "APPROVED",
                       "roles": {"BU_HEAD", "ADMIN"}, "notify": ["creator"]},
    "HOLD": {"from": {"APPROVED"}, "to": "ON_HOLD",
             "roles": {"BU_HEAD", "HR", "ADMIN"}, "notify": ["creator"]},               # INV-03
    "RESUME": {"from": {"ON_HOLD"}, "to": None,
               "roles": {"BU_HEAD", "HR", "ADMIN"}, "notify": ["creator"]},             # INV-03
    "CANCEL": {"from": {"PENDING_APPROVAL", "APPROVED"}, "to": "CANCELLED",
               "roles": {"BU_HEAD", "ADMIN"}, "notify": ["creator"]},
}


async def _write_history(db, rrf_id, from_status, to_status, comment, changed_by) -> int:
    row = await db.execute(
        text(
            "INSERT INTO rrf_status_history (rrf_id, from_status, to_status, comment, changed_by) "
            "VALUES (:rid, CAST(:fs AS rrf_status), CAST(:ts AS rrf_status), :c, :by) "
            "RETURNING history_id"
        ),
        {"rid": str(rrf_id), "fs": from_status, "ts": to_status, "c": comment, "by": str(changed_by)},
    )
    return int(row.scalar_one())


async def _resolve_recipients(db, rrf: RRF, targets: list[str]) -> list[str]:
    out: list[str] = []
    for t in targets:
        if t == "creator":
            out.append(str(rrf.created_by))
        elif t == "hr_rep" and rrf.hr_rep_user_id:
            out.append(str(rrf.hr_rep_user_id))
        elif t == "bu_head":
            uid = (
                await db.execute(
                    text("SELECT bu_head_user_id FROM business_units WHERE bu_id = :b"),
                    {"b": rrf.bu_id},
                )
            ).scalar_one_or_none()
            if uid:
                out.append(str(uid))
    return out


async def match_candidates(db: AsyncSession, user: User, rrf_id: uuid.UUID) -> dict:
    """AGENT-3: rank the active candidate pool for this RRF (advisory; ai_agent_runs logged)."""
    rrf = await rrf_repo.get_by_id(db, rrf_id)
    if rrf is None:
        raise NotFoundError("RRF not found", code="RMS-E-4041")
    # HR/ADMIN, or HM owner — BU_HEAD excluded (INV-07: no candidate access)
    if user.role_code not in ("HR", "ADMIN") and not (
        user.role_code == "HIRING_MANAGER" and rrf.created_by == user.user_id
    ):
        raise ForbiddenError("Not permitted to match candidates for this RRF", code="RMS-E-4031")

    rows = (
        await db.execute(
            text(
                "SELECT c.candidate_id, c.full_name, c.total_experience_years, c.cv_text, c.parsed_cv "
                "FROM applications a JOIN candidates c ON c.candidate_id = a.candidate_id "
                "WHERE a.rrf_id = :r AND a.status = 'ACTIVE' "
                "AND a.current_stage IN ('APPLIED','SCREENING','SHORTLISTED') LIMIT 10"
            ),
            {"r": str(rrf_id)},
        )
    ).fetchall()
    if not rows:
        return {"ranked": [], "method_note": "No active candidates in APPLIED..SHORTLISTED for this RRF."}

    canonical = [
        {"skill": s.skill.skill_name, "aliases": s.skill.aliases,
         "req_type": s.req_type, "priority": s.priority}
        for s in rrf.skills
    ]
    candidates = []
    for cid, name, exp, cv_text, parsed_cv in rows:
        skills_or_excerpt = None
        if parsed_cv and isinstance(parsed_cv, dict) and parsed_cv.get("skills"):
            skills_or_excerpt = parsed_cv["skills"]
        else:
            skills_or_excerpt = (cv_text or "")[:2000]
        candidates.append({
            "candidate_id": str(cid), "name": name,
            "experience_years": float(exp) if exp is not None else None,
            "skills_or_excerpt": skills_or_excerpt,
        })

    return await candidate_matching.run(
        rrf_id=rrf_id, canonical_skills=canonical,
        min_experience_years=float(rrf.min_experience_years),
        candidates=candidates, triggered_by=user.user_id,
    )


async def transition(db: AsyncSession, user: User, rrf_id: uuid.UUID, action: str, comment: str) -> dict:
    action = (action or "").upper()

    # INV-01: non-empty comment (also a DB CHECK on the history table)
    if not comment or not comment.strip():
        raise TransitionError("A non-empty comment is required for every transition", code="RMS-E-4222")

    rule = RRF_GUARD.get(action)
    if rule is None:
        raise TransitionError(f"Unknown action '{action}'", code="RMS-E-4221")

    rrf = await rrf_repo.get_by_id(db, rrf_id)
    if rrf is None:
        raise NotFoundError("RRF not found", code="RMS-E-4041")

    from_status = rrf.status
    if from_status not in rule["from"]:
        raise TransitionError(
            f"Transition {from_status}->{action} not permitted", code="RMS-E-4221"
        )

    # role gate
    if user.role_code not in rule["roles"]:
        raise ForbiddenError(
            f"Role {user.role_code} may not {action} this RRF", code="RMS-E-4031"
        )
    # row scope: HM must own; BU_HEAD limited to own BU (INV-07); ADMIN/HR unrestricted here
    if user.role_code == "HIRING_MANAGER" and rrf.created_by != user.user_id:
        raise ForbiddenError("Not the owner of this RRF", code="RMS-E-4031")
    if user.role_code == "BU_HEAD" and rrf.bu_id not in await rrf_repo.bu_ids_for_head(db, user.user_id):
        raise ForbiddenError("RRF is outside your business unit", code="RMS-E-4031")

    guard = rule.get("guard")
    if guard is not None:
        await guard(rrf)

    # resolve target status (RESUME returns to held_from_status per INV-03)
    to_status = rule["to"]
    if action == "RESUME":
        to_status = rrf.held_from_status or "APPROVED"

    # apply state + side effects
    rrf.status = to_status
    if action == "APPROVE":
        rrf.approved_by = user.user_id
        rrf.approved_at = func.now()
    if action == "HOLD":
        rrf.held_from_status = from_status
    if action == "RESUME":
        rrf.held_from_status = None
    rrf.updated_at = func.now()

    # INV-02: history + audit in the same transaction
    history_id = await _write_history(db, rrf_id, from_status, to_status, comment, user.user_id)
    await audit_service.record(
        db, entity_type="RRF", entity_id=str(rrf_id), action=f"TRANSITION:{action}",
        performed_by=user.user_id,
        before_state={"status": from_status},
        after_state={"status": to_status, "comment": comment},
    )

    # notifications to affected actors (same transaction)
    for uid in await _resolve_recipients(db, rrf, rule["notify"]):
        if uid != str(user.user_id):
            await notification_service.notify(
                db, user_id=uid, title=f"RRF {rrf.rrf_code}: {action}",
                body=comment, link_path=f"/rrfs/{rrf_id}",
            )

    await db.commit()
    return {
        "rrf_id": str(rrf_id), "from_status": from_status, "status": to_status,
        "action": action, "history_id": history_id,
    }
