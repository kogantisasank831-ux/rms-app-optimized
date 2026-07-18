"""pipeline_service — Application create + candidate-pipeline state machine (G6-G14).

Same data-driven guard-table approach as rrf_service. Stage lives in current_stage;
lifecycle status (ACTIVE/ON_HOLD/REJECTED/WITHDRAWN/HIRED) is separate (INV-03 hold/resume).
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import resume_screening
from app.core.config import settings
from app.db.session import SessionLocal
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TransitionError,
    ValidationError,
)
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.rrf import RRF
from app.models.user import User
from app.repositories import application_repo, user_repo
from app.services import audit_service, notification_service
from app.utils import pagination

import logging

_log = logging.getLogger("rms.pipeline")

_ACTIVE_STAGES = {  # stages from which reject/hold/withdraw are allowed
    "APPLIED", "SCREENING", "SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2",
    "INTERVIEW_MGMT", "OFFER", "OFFER_ACCEPTED",
}


# Ordered pipeline stages (index used for "strictly forward" checks).
STAGE_ORDER = [
    "APPLIED", "SCREENING", "SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2",
    "INTERVIEW_MGMT", "OFFER", "OFFER_ACCEPTED", "JOINED",
]
# Interview stages ↔ their interview round codes.
_STAGE_ROUND = {"INTERVIEW_R1": "R1_TECH", "INTERVIEW_R2": "R2_TECH", "INTERVIEW_MGMT": "MANAGEMENT"}
_INTERVIEW_STAGES = set(_STAGE_ROUND)
# Rounds are OPTIONAL: from shortlist or any interview round you may jump forward to any later
# interview round or straight to OFFER (skipping rounds). These are the "flexible band" stages.
_FLEX_FROM = {"SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT"}
_FLEX_TO = ["INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT", "OFFER"]


# --------------------------------------------------------------------------- guards
async def _guard_scheduled_round(db: AsyncSession, app: Application, round_code: str) -> None:
    """Landing on an interview stage requires that round to be scheduled first."""
    row = await db.execute(
        text(
            "SELECT 1 FROM interviews WHERE application_id = :aid "
            "AND round = CAST(:r AS interview_round) "
            "AND status = CAST('SCHEDULED' AS interview_status) LIMIT 1"
        ),
        {"aid": str(app.application_id), "r": round_code},
    )
    if row.first() is None:
        raise TransitionError(
            f"Schedule the {round_code} interview before moving the candidate into this round",
            code="RMS-E-4221",
        )


async def _guard_round_feedback(db: AsyncSession, app: Application, round_code: str) -> None:
    """Leaving an interview stage requires feedback for that exact round.

    This is enforced server-side as well as in the Kanban UI so a direct API call, stale browser,
    or concurrent hiring user cannot advance a candidate while the current evaluation is missing.
    """
    row = await db.execute(
        text(
            "SELECT 1 FROM interview_feedback f JOIN interviews i ON i.interview_id = f.interview_id "
            "WHERE i.application_id = :aid AND i.round = CAST(:r AS interview_round) LIMIT 1"
        ),
        {"aid": str(app.application_id), "r": round_code},
    )
    if row.first() is None:
        raise TransitionError(
            f"Record feedback for {round_code} before moving the candidate out of this round",
            code="RMS-E-4221",
        )


async def _guard_any_feedback(db: AsyncSession, app: Application) -> None:
    """An OFFER requires the candidate to have been evaluated in at least one interview round."""
    row = await db.execute(
        text(
            "SELECT 1 FROM interview_feedback f JOIN interviews i ON i.interview_id = f.interview_id "
            "WHERE i.application_id = :aid LIMIT 1"
        ),
        {"aid": str(app.application_id)},
    )
    if row.first() is None:
        raise TransitionError(
            "Record interview feedback for at least one round before extending an offer",
            code="RMS-E-4221",
        )


# Default single-step forward target from each stage (used when no explicit target_stage is given).
_DEFAULT_NEXT: dict[str, str] = {
    "APPLIED": "SCREENING",
    "SCREENING": "SHORTLISTED",
    "SHORTLISTED": "INTERVIEW_R1",
    "INTERVIEW_R1": "INTERVIEW_R2",
    "INTERVIEW_R2": "INTERVIEW_MGMT",
    "INTERVIEW_MGMT": "OFFER",
}


async def _resolve_advance(db: AsyncSession, app: Application, user: User, target_stage: str | None) -> str:
    """Validate an ADVANCE (optionally skipping rounds) and return the resolved target stage.

    Rounds are optional: from SHORTLISTED or any interview round the candidate may be moved to any
    LATER interview round or directly to OFFER. Early stages (APPLIED/SCREENING) stay single-step.
    """
    from_stage = app.current_stage
    if from_stage not in _DEFAULT_NEXT:
        raise TransitionError(f"Cannot ADVANCE from {from_stage}", code="RMS-E-4221")

    to = (target_stage or _DEFAULT_NEXT[from_stage]).upper()

    if from_stage in _FLEX_FROM:
        # any strictly-later stage within the interview/offer band
        allowed = [s for s in _FLEX_TO if STAGE_ORDER.index(s) > STAGE_ORDER.index(from_stage)]
        if to not in allowed:
            raise TransitionError(
                f"Cannot move from {from_stage} to {to}. Allowed: {', '.join(allowed)}",
                code="RMS-E-4221",
            )
    else:  # APPLIED / SCREENING — single step only
        if to != _DEFAULT_NEXT[from_stage]:
            raise TransitionError(
                f"From {from_stage} you can only advance to {_DEFAULT_NEXT[from_stage]}",
                code="RMS-E-4221",
            )

    roles = {"HR", "ADMIN"} if to == "OFFER" else {"HR", "HIRING_MANAGER", "ADMIN"}
    if user.role_code not in roles:
        raise ForbiddenError(f"Role {user.role_code} may not advance to {to}", code="RMS-E-4031")

    # The evaluation attached to the stage being left must be complete. Checking the exact
    # round prevents an older R1 assessment from accidentally authorising a later R2/management
    # move. The destination scheduling guard is evaluated afterwards.
    if from_stage in _INTERVIEW_STAGES:
        await _guard_round_feedback(db, app, _STAGE_ROUND[from_stage])

    if to in _INTERVIEW_STAGES:
        await _guard_scheduled_round(db, app, _STAGE_ROUND[to])
    elif to == "OFFER":
        await _guard_any_feedback(db, app)

    return to

# non-advance actions: allowed roles (row-scope for HM applied separately)
_ACTION_ROLES = {
    "REJECT": {"HR", "HIRING_MANAGER", "ADMIN"},
    "HOLD": {"HR", "HIRING_MANAGER", "ADMIN"},
    "RESUME": {"HR", "HIRING_MANAGER", "ADMIN"},
    "WITHDRAW": {"HR", "HIRING_MANAGER", "ADMIN"},
    "MARK_JOINED": {"HR", "ADMIN"},
    "ADVANCE": {"HR", "HIRING_MANAGER", "ADMIN"},  # refined per target stage in _resolve_advance
}


# --------------------------------------------------------------------------- helpers
async def _write_history(db, app_id, from_stage, to_stage, action, comment, acted_by) -> int:
    row = await db.execute(
        text(
            "INSERT INTO application_stage_history "
            "(application_id, from_stage, to_stage, action, comment, acted_by) "
            "VALUES (:aid, CAST(:fs AS app_stage), CAST(:ts AS app_stage), "
            "CAST(:act AS stage_action), :c, :by) RETURNING history_id"
        ),
        {"aid": str(app_id), "fs": from_stage, "ts": to_stage, "act": action,
         "c": comment, "by": str(acted_by)},
    )
    return int(row.scalar_one())


def _assert_hm_owns(user: User, app: Application) -> None:
    if user.role_code == "HIRING_MANAGER" and app.rrf.created_by != user.user_id:
        raise ForbiddenError("Application is not on one of your RRFs", code="RMS-E-4031")


def _top_skills(result: dict | None, limit: int = 3) -> list[str]:
    """Small set of skill tags for the pipeline card, drawn from the AI screen result."""
    if not isinstance(result, dict):
        return []
    skills: list[str] = []
    for cov in (result.get("essential_skill_coverage") or []):
        if isinstance(cov, dict) and cov.get("present") and cov.get("skill"):
            skills.append(str(cov["skill"]))
    for s in (result.get("desired_skills_found") or []):
        if s and str(s) not in skills:
            skills.append(str(s))
    return skills[:limit]


def serialize(app: Application) -> dict:
    cand = app.candidate
    return {
        "application_id": str(app.application_id),
        "rrf_id": str(app.rrf_id),
        "rrf_code": app.rrf.rrf_code,
        "candidate_id": str(app.candidate_id),
        "candidate_name": cand.full_name,
        "current_company": cand.current_company if cand else None,
        "experience_years": float(cand.total_experience_years) if cand and cand.total_experience_years is not None else None,
        "current_stage": app.current_stage,
        "status": app.status,
        "held_from_stage": app.held_from_stage,
        "ai_screen_score": float(app.ai_screen_score) if app.ai_screen_score is not None else None,
        "top_skills": _top_skills(app.ai_screen_result),
        "created_at": app.created_at,
        "updated_at": app.updated_at,
    }


# --------------------------------------------------------------------------- create
async def create_application(db: AsyncSession, user: User, rrf_id: str, candidate_id: str) -> dict:
    try:
        rid = uuid.UUID(rrf_id)
        cid = uuid.UUID(candidate_id)
    except ValueError as exc:
        raise ValidationError("invalid rrf_id or candidate_id", code="RMS-E-4001") from exc

    rrf = await db.get(RRF, rid)
    if rrf is None:
        raise ValidationError("RRF not found", code="RMS-E-4001")
    if rrf.status != "APPROVED":
        raise ValidationError("RRF must be APPROVED to accept applications", code="RMS-E-4001")

    candidate = await db.get(Candidate, cid)
    if candidate is None:
        raise ValidationError("Candidate not found", code="RMS-E-4001")

    if await application_repo.get_by_rrf_candidate(db, rid, cid) is not None:
        raise ConflictError("Candidate already applied to this RRF", code="RMS-E-4091")

    app = Application(rrf_id=rid, candidate_id=cid, current_stage="APPLIED", status="ACTIVE")
    db.add(app)
    await db.flush()
    await audit_service.record(
        db, entity_type="APPLICATION", entity_id=str(app.application_id), action="CREATE",
        performed_by=user.user_id, after_state={"rrf_id": rrf_id, "candidate_id": candidate_id},
    )

    # G6: auto-advance APPLIED -> SCREENING when CV text is available (agent scoring is T-206)
    stage = "APPLIED"
    if candidate.cv_text:
        await _write_history(db, app.application_id, "APPLIED", "SCREENING", "ADVANCE",
                             "Auto-advanced to SCREENING on intake (system)", user.user_id)
        app.current_stage = "SCREENING"
        stage = "SCREENING"
        await audit_service.record(
            db, entity_type="APPLICATION", entity_id=str(app.application_id),
            action="TRANSITION:AUTO_SCREEN", performed_by=user.user_id,
            before_state={"stage": "APPLIED"}, after_state={"stage": "SCREENING"},
        )

    await db.commit()

    # AGENT-1 auto-screen (best-effort; never blocks intake — LLD 6.1). Skipped under tests to
    # conserve Claude credits; the manual POST /applications/{id}/screen path is always available.
    # Detached from this request (asyncio.create_task, own DB session) so the ~60s Claude call does
    # NOT pin the request's pooled connection while it waits on the API — mirrors _spawn_summary.
    if stage == "SCREENING" and settings.AUTO_SCREEN_ON_CREATE and settings.APP_ENV != "test":
        _spawn_screen(app.application_id, user.user_id)

    return {"application_id": str(app.application_id), "current_stage": stage, "status": "ACTIVE"}


# Keep strong references so fire-and-forget tasks aren't garbage-collected mid-flight.
_bg_tasks: set[asyncio.Task] = set()


def _spawn_screen(application_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Schedule AGENT-1 auto-screen detached from the request. The application is already
    committed, so scheduling must never turn a successful intake into a 500."""
    try:
        task = asyncio.create_task(screen_application_bg(application_id, user_id))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
    except Exception:  # noqa: BLE001
        _log.exception("failed to schedule auto-screen for %s", application_id)


async def screen_application_bg(application_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fire-and-forget AGENT-1 auto-screen. Opens its OWN short-lived DB session (the request's
    session is closed once the response is sent) and never raises — an AI failure must not affect
    the already-saved application."""
    try:
        async with SessionLocal() as db:
            user = await user_repo.get_by_id(db, user_id)
            if user is None:
                return
            await screen_application(db, user, application_id)
    except Exception as exc:  # noqa: BLE001 — best-effort; log and move on
        _log.warning("auto-screen failed for %s: %s", application_id, exc)


# --------------------------------------------------------------------------- read
async def list_applications(
    db: AsyncSession, user: User, *, rrf_id: str | None, stage: str | None,
    status: str | None, page: int, limit: int, q: str | None = None, sort: str = "recent",
) -> tuple[list[dict], dict]:
    p = pagination.resolve(page, limit)
    rid = uuid.UUID(rrf_id) if rrf_id else None
    hm_id = user.user_id if user.role_code == "HIRING_MANAGER" else None
    rows, total = await application_repo.list_scoped(
        db, rrf_id=rid, stage=stage, status=status, hm_user_id=hm_id,
        q=q, sort=sort, limit=p.limit, offset=p.offset,
    )
    items = [serialize(a) for a in rows]
    fb_done = await _current_round_feedback_ids(db, rows)
    for it in items:
        it["current_round_feedback"] = it["application_id"] in fb_done
    return items, pagination.meta(p, total)


async def _current_round_feedback_ids(db: AsyncSession, rows: list[Application]) -> set[str]:
    """Of the given applications sitting in an interview stage, which already have submitted
    feedback for that stage's round. One query, no N+1."""
    from app.models.feedback import InterviewFeedback
    from app.models.interview import Interview

    targets = {str(a.application_id): _STAGE_ROUND[a.current_stage] for a in rows if a.current_stage in _STAGE_ROUND}
    if not targets:
        return set()
    pairs = (
        await db.execute(
            select(Interview.application_id, Interview.round)
            .join(InterviewFeedback, InterviewFeedback.interview_id == Interview.interview_id)
            .where(Interview.application_id.in_([uuid.UUID(i) for i in targets]))
        )
    ).all()
    return {str(aid) for aid, rnd in pairs if targets.get(str(aid)) == rnd}


async def pipeline_stats(db: AsyncSession, user: User, rrf_id: str) -> dict:
    """Per-requisition headline stats for the pipeline board KPI row."""
    rid = uuid.UUID(rrf_id)
    hm = "AND a.rrf_id IN (SELECT rrf_id FROM rrf WHERE created_by = :uid)" if user.role_code == "HIRING_MANAGER" else ""
    p: dict = {"rid": str(rid)}
    if hm:
        p["uid"] = str(user.user_id)
    row = (await db.execute(text(f"""
        SELECT
          (SELECT count(*) FROM applications a WHERE a.rrf_id=:rid AND a.status='ACTIVE' {hm}) AS active,
          (SELECT count(*) FROM applications a WHERE a.rrf_id=:rid AND a.created_at >= now() - interval '7 days' {hm}) AS added_week,
          (SELECT AVG(EXTRACT(EPOCH FROM (now() - a.updated_at))/86400) FROM applications a WHERE a.rrf_id=:rid AND a.status='ACTIVE' {hm}) AS avg_days,
          (SELECT count(*) FROM applications a WHERE a.rrf_id=:rid AND a.current_stage IN ('INTERVIEW_R1','INTERVIEW_R2','INTERVIEW_MGMT','OFFER','OFFER_ACCEPTED','JOINED') {hm}) AS reached_iv,
          (SELECT count(*) FROM applications a WHERE a.rrf_id=:rid AND a.status <> 'WITHDRAWN' {hm}) AS base_total,
          (SELECT count(*) FROM offers o JOIN applications a ON a.application_id=o.application_id WHERE a.rrf_id=:rid AND o.status<>'DRAFT' {hm}) AS offers_released,
          (SELECT count(*) FROM offers o JOIN applications a ON a.application_id=o.application_id WHERE a.rrf_id=:rid AND o.status='ACCEPTED' {hm}) AS offers_accepted
    """), p)).mappings().one()

    base = int(row["base_total"] or 0)
    released = int(row["offers_released"] or 0)
    accepted = int(row["offers_accepted"] or 0)
    avg_days = row["avg_days"]
    return {
        "active_candidates": int(row["active"] or 0),
        "added_this_week": int(row["added_week"] or 0),
        "avg_days_in_stage": round(float(avg_days), 1) if avg_days is not None else None,
        "interview_conversion": round(int(row["reached_iv"] or 0) / base, 3) if base else 0.0,
        "offers_released": released,
        "offers_pending": max(released - accepted, 0),
        "offer_acceptance": round(accepted / released, 3) if released else 0.0,
    }


async def get_application(db: AsyncSession, user: User, application_id: uuid.UUID) -> dict:
    app = await application_repo.get_by_id(db, application_id)
    if app is None:
        raise NotFoundError("Application not found", code="RMS-E-4041")
    _assert_hm_owns(user, app)
    data = serialize(app)
    data["ai_screen_result"] = app.ai_screen_result  # full agent output for the ScreeningResult card
    return data


# --------------------------------------------------------------------------- screening (AGENT-1)
async def _latest_jd_markdown(db: AsyncSession, rrf_id: uuid.UUID) -> str | None:
    row = await db.execute(
        text("SELECT jd_markdown FROM rrf_jd_versions WHERE rrf_id = :r ORDER BY version_no DESC LIMIT 1"),
        {"r": str(rrf_id)},
    )
    return row.scalar_one_or_none()


def _fallback_jd(rrf: RRF) -> str:
    skills = ", ".join(s.skill.skill_name for s in rrf.skills)
    return (
        f"Role: {rrf.position_title}\nProject: {rrf.project_name}\n"
        f"Responsibilities: {rrf.responsibilities or 'N/A'}\n"
        f"Required skills: {skills}\nMinimum experience: {rrf.min_experience_years} years"
    )


async def screen_application(db: AsyncSession, user: User, application_id: uuid.UUID) -> dict:
    """Run resume_screening and persist score + full result on the application (AGENT-1)."""
    app = await application_repo.get_by_id(db, application_id)
    if app is None:
        raise NotFoundError("Application not found", code="RMS-E-4041")

    rrf, cand = app.rrf, app.candidate
    essential = [f"{s.skill.skill_name} (priority {s.priority})"
                 for s in rrf.skills if s.req_type == "ESSENTIAL"]
    desired = [s.skill.skill_name for s in rrf.skills if s.req_type == "DESIRED"]
    jd = await _latest_jd_markdown(db, rrf.rrf_id) or _fallback_jd(rrf)

    result = await resume_screening.run(
        application_id=application_id,
        position_title=rrf.position_title,
        min_experience_years=float(rrf.min_experience_years),
        jd_markdown=jd,
        essential_skills=essential,
        desired_skills=desired,
        cv_text=cand.cv_text or "",
        candidate_experience_years=float(cand.total_experience_years)
        if cand.total_experience_years is not None else None,
        triggered_by=user.user_id,
    )

    score = result.get("match_score")
    app.ai_screen_score = score
    app.ai_screen_result = result
    app.updated_at = func.now()
    await audit_service.record(
        db, entity_type="APPLICATION", entity_id=str(application_id), action="SCREEN",
        performed_by=user.user_id,
        after_state={"match_score": score, "recommendation": result.get("recommendation")},
    )
    await db.commit()
    return {
        "application_id": str(application_id),
        "ai_screen_score": float(score) if score is not None else None,
        "recommendation": result.get("recommendation"),
        "result": result,
    }


async def get_history(db: AsyncSession, user: User, application_id: uuid.UUID) -> list[dict]:
    app = await application_repo.get_by_id(db, application_id)
    if app is None:
        raise NotFoundError("Application not found", code="RMS-E-4041")
    _assert_hm_owns(user, app)
    rows = await db.execute(
        text(
            "SELECT history_id, from_stage, to_stage, action, comment, acted_by, acted_at "
            "FROM application_stage_history WHERE application_id = :aid ORDER BY acted_at"
        ),
        {"aid": str(application_id)},
    )
    return [
        {"history_id": r[0], "from_stage": r[1], "to_stage": r[2], "action": r[3],
         "comment": r[4], "acted_by": str(r[5]), "acted_at": r[6].isoformat()}
        for r in rows.fetchall()
    ]


# --------------------------------------------------------------------------- transition (G6-G14)
async def transition(
    db: AsyncSession, user: User, application_id: uuid.UUID, action: str, comment: str,
    target_stage: str | None = None,
) -> dict:
    action = (action or "").upper()
    if not comment or not comment.strip():
        raise TransitionError("A non-empty comment is required for every transition", code="RMS-E-4222")
    if action not in _ACTION_ROLES:
        raise TransitionError(f"Unknown action '{action}'", code="RMS-E-4221")

    # Serialize transitions for this application. Without a row lock, two hiring users can both
    # read the same stage, pass the guards, and write conflicting history/stage changes.
    if not await application_repo.lock_by_id(db, application_id):
        raise NotFoundError("Application not found", code="RMS-E-4041")
    app = await application_repo.get_by_id(db, application_id)
    if app is None:  # defensive: the row is locked, so this should only happen on DB failure
        raise NotFoundError("Application not found", code="RMS-E-4041")
    _assert_hm_owns(user, app)

    from_stage = app.current_stage
    from_status = app.status
    to_stage = from_stage
    # value for the stage_action enum column; MARK_JOINED is recorded as an ADVANCE (no such enum value)
    stage_action = "ADVANCE" if action == "MARK_JOINED" else action

    if action == "ADVANCE":
        if from_status != "ACTIVE":
            raise TransitionError(f"Cannot ADVANCE from {from_stage}/{from_status}", code="RMS-E-4221")
        to_stage = await _resolve_advance(db, app, user, target_stage)
        app.current_stage = to_stage

    elif action == "MARK_JOINED":
        if user.role_code not in _ACTION_ROLES["MARK_JOINED"]:
            raise ForbiddenError("Not permitted to mark joined", code="RMS-E-4031")
        if from_stage != "OFFER_ACCEPTED" or from_status != "ACTIVE":
            raise TransitionError("Only an OFFER_ACCEPTED application can be marked JOINED", code="RMS-E-4221")
        to_stage = "JOINED"
        app.current_stage = "JOINED"
        app.status = "HIRED"
        await _close_rrf_if_full(db, app, user)

    else:
        if user.role_code not in _ACTION_ROLES[action]:
            raise ForbiddenError(f"Role {user.role_code} may not {action}", code="RMS-E-4031")
        if action in ("REJECT", "HOLD", "WITHDRAW"):
            if from_status != "ACTIVE" or from_stage not in _ACTIVE_STAGES:
                raise TransitionError(f"Cannot {action} from {from_stage}/{from_status}", code="RMS-E-4221")
            if action == "REJECT":
                app.status = "REJECTED"
            elif action == "WITHDRAW":
                app.status = "WITHDRAWN"
            else:  # HOLD (INV-03)
                app.held_from_stage = from_stage
                app.status = "ON_HOLD"
        elif action == "RESUME":
            if from_status != "ON_HOLD":
                raise TransitionError("Only an ON_HOLD application can be resumed", code="RMS-E-4221")
            to_stage = app.held_from_stage or from_stage
            app.current_stage = to_stage
            app.status = "ACTIVE"
            app.held_from_stage = None

    app.updated_at = func.now()

    # INV-02: history + audit in the same transaction
    history_id = await _write_history(db, application_id, from_stage, to_stage, stage_action, comment, user.user_id)
    await audit_service.record(
        db, entity_type="APPLICATION", entity_id=str(application_id), action=f"TRANSITION:{action}",
        performed_by=user.user_id,
        before_state={"stage": from_stage, "status": from_status},
        after_state={"stage": app.current_stage, "status": app.status, "comment": comment},
    )
    # notify candidate's RRF owner (HM) on meaningful transitions
    if app.rrf.created_by != user.user_id:
        await notification_service.notify(
            db, user_id=app.rrf.created_by,
            title=f"Application {app.candidate.full_name}: {action}",
            body=comment, link_path=f"/applications/{application_id}",
        )

    await db.commit()
    return {
        "application_id": str(application_id), "from_stage": from_stage,
        "current_stage": app.current_stage, "status": app.status,
        "action": action, "history_id": history_id,
    }


async def system_move_to_offer(db: AsyncSession, actor: User, app: Application, comment: str) -> None:
    """Advance an application into the OFFER stage as a side effect of creating an offer.

    Idempotent (no-op if already OFFER). Shares the offer's transaction (no commit). Eligible from
    the shortlist or any interview round — interview rounds are optional (see _resolve_advance)."""
    if app.current_stage == "OFFER":
        return
    if app.status != "ACTIVE":
        raise TransitionError("Only an active application can be moved to OFFER", code="RMS-E-4221")
    if app.current_stage not in _FLEX_FROM:  # SHORTLISTED / INTERVIEW_R1 / R2 / MGMT
        raise TransitionError(
            f"Cannot create an offer from stage {app.current_stage} — shortlist the candidate first",
            code="RMS-E-4221",
        )
    from_stage = app.current_stage
    app.current_stage = "OFFER"
    app.updated_at = func.now()
    await _write_history(db, app.application_id, from_stage, "OFFER", "ADVANCE", comment, actor.user_id)
    await audit_service.record(
        db, entity_type="APPLICATION", entity_id=str(app.application_id),
        action="TRANSITION:OFFER", performed_by=actor.user_id,
        before_state={"stage": from_stage}, after_state={"stage": "OFFER", "comment": comment},
    )


async def system_offer_accepted(db: AsyncSession, actor: User, application_id: uuid.UUID, comment: str) -> None:
    """G11: OFFER -> OFFER_ACCEPTED, driven by offer acceptance. Shares the offer txn (no commit)."""
    app = await application_repo.get_by_id(db, application_id)
    if app is None or app.current_stage != "OFFER" or app.status != "ACTIVE":
        raise TransitionError("Application is not in OFFER stage", code="RMS-E-4221")
    app.current_stage = "OFFER_ACCEPTED"
    app.updated_at = func.now()
    await _write_history(db, application_id, "OFFER", "OFFER_ACCEPTED", "ADVANCE", comment, actor.user_id)
    await audit_service.record(
        db, entity_type="APPLICATION", entity_id=str(application_id), action="TRANSITION:OFFER_ACCEPTED",
        performed_by=actor.user_id, before_state={"stage": "OFFER"},
        after_state={"stage": "OFFER_ACCEPTED", "comment": comment},
    )


async def system_offer_declined(db: AsyncSession, actor: User, application_id: uuid.UUID, comment: str) -> None:
    """G13: offer declined -> application REJECTED. Shares the offer txn (no commit)."""
    app = await application_repo.get_by_id(db, application_id)
    if app is None or app.current_stage != "OFFER" or app.status != "ACTIVE":
        raise TransitionError("Application is not in OFFER stage", code="RMS-E-4221")
    from_stage = app.current_stage
    app.status = "REJECTED"
    app.updated_at = func.now()
    await _write_history(db, application_id, from_stage, from_stage, "REJECT",
                         f"{comment} (OFFER_DECLINED)", actor.user_id)
    await audit_service.record(
        db, entity_type="APPLICATION", entity_id=str(application_id), action="TRANSITION:OFFER_DECLINED",
        performed_by=actor.user_id, before_state={"stage": from_stage, "status": "ACTIVE"},
        after_state={"stage": from_stage, "status": "REJECTED", "reason": "OFFER_DECLINED"},
    )


async def _close_rrf_if_full(db: AsyncSession, app: Application, user: User) -> None:
    """G12 side effect: bump positions_filled; auto-CLOSE the RRF when fully staffed."""
    rrf = app.rrf
    rrf.positions_filled = (rrf.positions_filled or 0) + 1
    if rrf.positions_filled >= rrf.positions_count and rrf.status == "APPROVED":
        prev = rrf.status
        rrf.status = "CLOSED"
        await db.execute(
            text(
                "INSERT INTO rrf_status_history (rrf_id, from_status, to_status, comment, changed_by) "
                "VALUES (:rid, CAST(:fs AS rrf_status), CAST(:ts AS rrf_status), :c, :by)"
            ),
            {"rid": str(rrf.rrf_id), "fs": prev, "ts": "CLOSED",
             "c": "Auto-closed: all positions filled (system)", "by": str(user.user_id)},
        )
