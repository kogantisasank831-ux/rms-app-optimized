"""interview_service — scheduling (panel 1..5, INV-05), my-interviews, cancel/no-show/reschedule.

Feedback (G15 SCHEDULED->COMPLETED) is handled in T-303.
"""
from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import feedback_summarization, interview_questions, interview_scheduling
from app.core.config import settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TransitionError,
    ValidationError,
)
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.feedback import InterviewFeedback, InterviewSkillRating
from app.models.interview import Interview, InterviewPanelist
from app.models.skill import SkillMaster
from app.models.user import User
from app.db.session import SessionLocal
from app.repositories import application_repo, interview_repo, user_repo
from app.services import audit_service, notification_service

_ACTIVE_APP_STATUS = "ACTIVE"
_ROUND_ORDER = {"R1_TECH": 1, "R2_TECH": 2, "MANAGEMENT": 3}
_ROUND_PREDECESSOR = {"R1_TECH": "SHORTLISTED", "R2_TECH": "INTERVIEW_R1", "MANAGEMENT": "INTERVIEW_R2"}
_log = logging.getLogger("rms.interview")


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(f"invalid uuid for {field}", code="RMS-E-4001") from exc


def _validate_window(start: datetime.datetime, end: datetime.datetime) -> None:
    """Require an explicit timezone and a future, positive interview window."""
    if start.tzinfo is None or start.utcoffset() is None or end.tzinfo is None or end.utcoffset() is None:
        raise ValidationError(
            "scheduled_start and scheduled_end must include a timezone offset",
            code="RMS-E-4001",
        )
    if end <= start:
        raise ValidationError("scheduled_end must be after scheduled_start", code="RMS-E-4001")
    if start < datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1):
        raise ValidationError("scheduled_start cannot be in the past", code="RMS-E-4001")


def serialize(iv: Interview) -> dict:
    return {
        "interview_id": str(iv.interview_id),
        "application_id": str(iv.application_id),
        "round": iv.round,
        "scheduled_start": iv.scheduled_start,
        "scheduled_end": iv.scheduled_end,
        "mode": iv.mode,
        "meeting_link": iv.meeting_link,
        "location": iv.location,
        "status": iv.status,
        "rescheduled_from": str(iv.rescheduled_from) if iv.rescheduled_from else None,
        "panelists": [
            {"user_id": str(p.user_id), "full_name": p.user.full_name, "is_lead": p.is_lead}
            for p in iv.panelists
        ],
    }


async def _validate_panel(db: AsyncSession, panelists) -> list[uuid.UUID]:
    if not (1 <= len(panelists) <= 5):
        raise ValidationError("Interview panel size must be 1..5", code="RMS-E-4224")  # INV-05
    if sum(1 for p in panelists if p.is_lead) != 1:
        raise ValidationError("Exactly one panelist must be the lead", code="RMS-E-4001")
    ids = [_parse_uuid(p.user_id, "panelist.user_id") for p in panelists]
    if len(set(ids)) != len(ids):
        raise ValidationError("Duplicate panelist", code="RMS-E-4001")
    found = (
        await db.execute(select(func.count()).select_from(
            select(User.user_id).where(User.user_id.in_(ids), User.is_active.is_(True)).subquery()
        ))
    ).scalar_one()
    if found != len(ids):
        raise ValidationError("One or more panelists not found or inactive", code="RMS-E-4001")
    return ids


async def schedule(db: AsyncSession, user: User, payload) -> dict:
    app_id = _parse_uuid(payload.application_id, "application_id")
    app = await application_repo.get_by_id(db, app_id)
    if app is None:
        raise ValidationError("Application not found", code="RMS-E-4001")
    if app.status != _ACTIVE_APP_STATUS:
        raise ValidationError("Cannot schedule an interview for a non-active application", code="RMS-E-4001")
    _validate_window(payload.scheduled_start, payload.scheduled_end)

    await _validate_panel(db, payload.panelists)

    iv = Interview(
        application_id=app_id,
        round=payload.round,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        mode=payload.mode,
        meeting_link=payload.meeting_link,
        location=payload.location,
        status="SCHEDULED",
        created_by=user.user_id,
    )
    for p in payload.panelists:
        iv.panelists.append(InterviewPanelist(user_id=uuid.UUID(p.user_id), is_lead=p.is_lead))
    db.add(iv)
    await db.flush()

    await audit_service.record(
        db, entity_type="INTERVIEW", entity_id=str(iv.interview_id), action="CREATE",
        performed_by=user.user_id,
        after_state={"application_id": str(app_id), "round": payload.round, "status": "SCHEDULED"},
    )
    for p in payload.panelists:
        await notification_service.notify(
            db, user_id=p.user_id, title=f"Interview scheduled: {payload.round}",
            body=f"You are on the panel for an interview on {payload.scheduled_start}",
            link_path=f"/interviews/{iv.interview_id}",
        )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "An active interview already exists for this application/round", code="RMS-E-4091"
        ) from exc

    # Auto-advance the pipeline stage to match the scheduled round, so the candidate card moves
    # into the correct Round column immediately. Best-effort: only advances one step from the
    # expected predecessor stage and still honours all pipeline guards (e.g. prior-round feedback),
    # and never fails the scheduling call.
    predecessor = _ROUND_PREDECESSOR.get(payload.round)
    fresh_app = await application_repo.get_by_id(db, app_id)
    if predecessor and fresh_app is not None and fresh_app.current_stage == predecessor and fresh_app.status == _ACTIVE_APP_STATUS:
        from app.services import pipeline_service
        try:
            await pipeline_service.transition(
                db, user, app_id, "ADVANCE",
                f"Auto-advanced on scheduling {payload.round} interview (system)",
            )
        except Exception as exc:  # noqa: BLE001 — auto-advance must never block scheduling
            # transition() may have started a transaction or hit a DB exception. Reset the
            # session before issuing the response query; otherwise a successfully committed
            # interview can still surface as a spurious 500/PendingRollbackError.
            await db.rollback()
            _log.warning("auto-advance after scheduling failed for %s: %s", app_id, exc)

    refreshed = await interview_repo.get_by_id(db, iv.interview_id)
    latest_app = await application_repo.get_by_id(db, app_id)
    result = serialize(refreshed)
    # The client uses this authoritative value to decide whether the auto-advance completed or a
    # deferred explicit move is still needed. This removes stale-closure and duplicate-move races.
    result["application_stage"] = latest_app.current_stage if latest_app is not None else app.current_stage
    return result


def _parse_iso(value: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _overlaps(s1, e1, s2, e2) -> bool:
    return s1 < e2 and s2 < e1


async def suggest_slots(db: AsyncSession, user: User, payload) -> dict:
    """AGENT-4: propose conflict-free slots, then deterministically re-verify non-overlap."""
    panelist_ids = [_parse_uuid(p, "panelist_id") for p in payload.panelist_ids]
    if not (1 <= len(panelist_ids) <= 5):
        raise ValidationError("panelist_ids size must be 1..5", code="RMS-E-4224")

    # gather each panelist's SCHEDULED busy intervals
    busy: dict[str, list[tuple]] = {str(pid): [] for pid in panelist_ids}
    rows = (
        await db.execute(
            select(InterviewPanelist.user_id, Interview.scheduled_start, Interview.scheduled_end)
            .join(Interview, Interview.interview_id == InterviewPanelist.interview_id)
            .where(InterviewPanelist.user_id.in_(panelist_ids), Interview.status == "SCHEDULED")
        )
    ).all()
    for uid, s, e in rows:
        busy.setdefault(str(uid), []).append((s, e))

    candidate_windows = [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in payload.candidate_windows]
    panelists_payload = [
        {"user_id": str(pid), "busy": [{"start": s.isoformat(), "end": e.isoformat()} for s, e in busy[str(pid)]]}
        for pid in panelist_ids
    ]

    result = await interview_scheduling.run(
        application_id=_parse_uuid(payload.application_id, "application_id"),
        round=payload.round,
        candidate_windows=candidate_windows,
        panelists=panelists_payload,
        triggered_by=user.user_id,
    )

    # deterministic re-check: agent output is advisory (LLD 6.5)
    for proposal in result.get("proposals", []):
        ps, pe = _parse_iso(proposal.get("start", "")), _parse_iso(proposal.get("end", ""))
        verified = ps is not None and pe is not None and pe > ps
        if verified:
            for intervals in busy.values():
                if any(_overlaps(ps, pe, bs, be) for bs, be in intervals):
                    verified = False
                    break
        proposal["verified"] = verified

    return result


async def list_my(db: AsyncSession, user: User) -> list[dict]:
    rows = (
        await db.execute(
            select(Interview, Candidate.full_name)
            .join(InterviewPanelist, InterviewPanelist.interview_id == Interview.interview_id)
            .join(Application, Application.application_id == Interview.application_id)
            .join(Candidate, Candidate.candidate_id == Application.candidate_id)
            .where(InterviewPanelist.user_id == user.user_id)
            .order_by(Interview.scheduled_start)
        )
    ).unique().all()
    return [{**serialize(iv), "candidate_name": name} for iv, name in rows]


async def list_by_application(db: AsyncSession, user: User, application_id: uuid.UUID) -> list[dict]:
    app = await application_repo.get_by_id(db, application_id)
    if app is None:
        raise NotFoundError("Application not found", code="RMS-E-4041")
    if user.role_code == "HIRING_MANAGER" and app.rrf.created_by != user.user_id:
        raise ForbiddenError("Not permitted to view these interviews", code="RMS-E-4031")
    rows = await interview_repo.list_by_application(db, application_id)
    return [serialize(iv) for iv in rows]


async def patch(db: AsyncSession, user: User, interview_id: uuid.UUID, payload) -> dict:
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")
    if not payload.comment or not payload.comment.strip():
        raise TransitionError("A non-empty comment is required", code="RMS-E-4222")
    if iv.status != "SCHEDULED":
        raise TransitionError(f"Cannot {payload.action} an interview in status {iv.status}", code="RMS-E-4221")

    action = payload.action
    result_iv = iv

    if action == "CANCEL":
        iv.status = "CANCELLED"
    elif action == "NO_SHOW":
        iv.status = "NO_SHOW"
    else:  # RESCHEDULE -> new SCHEDULED row, old becomes RESCHEDULED
        if payload.scheduled_start is None or payload.scheduled_end is None:
            raise ValidationError("RESCHEDULE requires scheduled_start and scheduled_end", code="RMS-E-4001")
        _validate_window(payload.scheduled_start, payload.scheduled_end)
        new_iv = Interview(
            application_id=iv.application_id, round=iv.round,
            scheduled_start=payload.scheduled_start, scheduled_end=payload.scheduled_end,
            mode=iv.mode, meeting_link=iv.meeting_link, location=iv.location,
            status="SCHEDULED", rescheduled_from=iv.interview_id, created_by=user.user_id,
        )
        for p in iv.panelists:
            new_iv.panelists.append(InterviewPanelist(user_id=p.user_id, is_lead=p.is_lead))
        iv.status = "RESCHEDULED"
        db.add(new_iv)
        await db.flush()
        result_iv = new_iv

    await audit_service.record(
        db, entity_type="INTERVIEW", entity_id=str(interview_id), action=f"PATCH:{action}",
        performed_by=user.user_id,
        before_state={"status": "SCHEDULED"},
        after_state={"status": iv.status, "comment": payload.comment,
                     "new_interview_id": str(result_iv.interview_id) if action == "RESCHEDULE" else None},
    )
    for p in iv.panelists:
        await notification_service.notify(
            db, user_id=p.user_id, title=f"Interview {action}: {iv.round}",
            body=payload.comment, link_path=f"/interviews/{result_iv.interview_id}",
        )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Interview scheduling conflict", code="RMS-E-4091") from exc

    refreshed = await interview_repo.get_by_id(db, result_iv.interview_id)
    return serialize(refreshed)


# =========================================================================== #
# CONSOLIDATED FEEDBACK (G15, INV-04) + PRIOR-FEEDBACK (INV-06)                #
# =========================================================================== #
def _assessments_of(attributes: dict | None) -> list[dict]:
    """Category assessments (behavioural/technical/process_knowledge) live under
    attributes['assessments']; return them as a stable list for API responses."""
    items = (attributes or {}).get("assessments") or []
    return [
        {"category": a.get("category"), "rating": a.get("rating"), "comments": a.get("comments")}
        for a in items if isinstance(a, dict) and a.get("category")
    ]


def _feedback_out(fb: InterviewFeedback, interview_status: str) -> dict:
    return {
        "feedback_id": str(fb.feedback_id),
        "interview_id": str(fb.interview_id),
        "overall_rating": float(fb.overall_rating),
        "recommendation": fb.recommendation,
        "strengths": fb.strengths,
        "weaknesses": fb.weaknesses,
        "raw_notes": fb.raw_notes,
        "attributes": fb.attributes or {},
        "assessments": _assessments_of(fb.attributes),
        "ai_summary": fb.ai_summary,
        "skill_ratings": [
            {"skill_id": r.skill_id, "skill_name": r.skill.skill_name,
             "rating": r.rating, "remarks": r.remarks}
            for r in fb.skill_ratings
        ],
        "interview_status": interview_status,
    }


async def submit_feedback(db: AsyncSession, user: User, interview_id: uuid.UUID, payload) -> dict:
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")

    # only the lead panelist or HR/ADMIN may submit (LLD 4.4 G15)
    is_lead = any(p.is_lead and p.user_id == user.user_id for p in iv.panelists)
    if user.role_code not in ("HR", "ADMIN") and not is_lead:
        raise ForbiddenError("Only the lead panelist or HR/ADMIN may submit feedback", code="RMS-E-4031")

    # INV-04 (checked before the status guard so a duplicate returns the precise 4223, not 4221)
    existing = (
        await db.execute(select(InterviewFeedback).where(InterviewFeedback.interview_id == interview_id))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("Consolidated feedback already exists for this interview", code="RMS-E-4223")
    if iv.status != "SCHEDULED":
        raise TransitionError(f"Cannot submit feedback for interview in status {iv.status}", code="RMS-E-4221")

    # Resolve skill names up front so the response can be serialized BEFORE commit — see the
    # serialization note below. Doubles as the "skill_id exists" validation.
    skill_names: dict[int, str] = {}
    if payload.skill_ratings:
        ids = {sr.skill_id for sr in payload.skill_ratings}
        rows = (
            await db.execute(
                select(SkillMaster.skill_id, SkillMaster.skill_name).where(SkillMaster.skill_id.in_(ids))
            )
        ).all()
        skill_names = {row.skill_id: row.skill_name for row in rows}
        if len(skill_names) != len(ids):
            raise ValidationError("One or more skill_id not found", code="RMS-E-4001")

    # Behavioural is always required. Technical/process_knowledge apply only to technical
    # rounds (R1/R2); the Management round is behavioural-only.
    assessments = getattr(payload, "assessments", None) or []
    rated = {a.category for a in assessments if a.rating is not None}
    required = ["behavioural"] if iv.round == "MANAGEMENT" else ["behavioural", "technical"]
    missing = [c for c in required if c not in rated]
    if assessments and missing:
        raise ValidationError(
            f"A rating is required for: {', '.join(missing)}", code="RMS-E-4001"
        )

    # Fold the structured category assessments into attributes (JSONB) so they persist,
    # round-trip in responses, and reach the AI summarizer without a schema migration.
    attributes = dict(payload.attributes or {})
    if assessments:
        attributes["assessments"] = [a.model_dump() for a in assessments]

    fb = InterviewFeedback(
        interview_id=interview_id,
        overall_rating=payload.overall_rating,
        recommendation=payload.recommendation,
        strengths=payload.strengths,
        weaknesses=payload.weaknesses,
        raw_notes=payload.raw_notes,
        attributes=attributes,
        submitted_by=user.user_id,
    )
    for sr in payload.skill_ratings:
        fb.skill_ratings.append(
            InterviewSkillRating(skill_id=sr.skill_id, rating=sr.rating, remarks=sr.remarks)
        )
    iv.status = "COMPLETED"  # G15: SCHEDULED -> COMPLETED
    db.add(fb)
    await db.flush()

    await audit_service.record(
        db, entity_type="INTERVIEW", entity_id=str(interview_id), action="FEEDBACK_SUBMITTED",
        performed_by=user.user_id,
        after_state={"recommendation": payload.recommendation,
                     "overall_rating": payload.overall_rating, "interview_status": "COMPLETED"},
    )
    # notify the RRF owner (HM) that a round is complete
    app = await application_repo.get_by_id(db, iv.application_id)
    if app is not None and app.rrf.created_by != user.user_id:
        await notification_service.notify(
            db, user_id=app.rrf.created_by, title=f"Interview feedback submitted: {iv.round}",
            body=f"Recommendation: {payload.recommendation}", link_path=f"/interviews/{interview_id}",
        )

    # Serialize BEFORE commit. SQLAlchemy expires all attributes on commit (expire_on_commit),
    # so touching fb.* / fb.skill_ratings[].skill afterwards would fire an async lazy-load and
    # raise MissingGreenlet — turning an already-committed feedback into a spurious 500. Building
    # the dict here uses only in-memory values (fb is populated after flush) + the skill_names map.
    result = {
        "feedback_id": str(fb.feedback_id),
        "interview_id": str(interview_id),
        "overall_rating": float(fb.overall_rating),
        "recommendation": fb.recommendation,
        "strengths": fb.strengths,
        "weaknesses": fb.weaknesses,
        "raw_notes": fb.raw_notes,
        "attributes": attributes or {},
        "assessments": _assessments_of(attributes),
        "ai_summary": None,  # AGENT-5 summary is generated in the background after this response
        "skill_ratings": [
            {"skill_id": sr.skill_id, "skill_name": skill_names.get(sr.skill_id, ""),
             "rating": sr.rating, "remarks": sr.remarks}
            for sr in payload.skill_ratings
        ],
        "interview_status": "COMPLETED",
    }

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Consolidated feedback already exists for this interview", code="RMS-E-4223") from exc

    # AGENT-5 auto-summarize runs AFTER the response is returned (scheduled by the router as a
    # background task). We must NOT await the Claude call here — it can take tens of seconds and
    # would block the HTTP response even though the feedback is already committed above.
    return result


async def summarize_feedback_bg(interview_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fire-and-forget AGENT-5 summarization, run from a FastAPI BackgroundTask.

    Opens its own DB session (the request's session is closed once the response is sent) and
    never raises — an AI failure must not affect the already-saved feedback."""
    if not settings.AUTO_SUMMARIZE_FEEDBACK or settings.APP_ENV == "test":
        return
    try:
        async with SessionLocal() as db:
            user = await user_repo.get_by_id(db, user_id)
            if user is None:
                return
            await summarize_feedback(db, user, interview_id)
    except Exception as exc:  # noqa: BLE001 — best-effort; log and move on
        _log.warning("auto-summarize failed for %s: %s", interview_id, exc)


async def summarize_feedback(db: AsyncSession, user: User, interview_id: uuid.UUID) -> dict:
    """Run feedback_summarization on the saved consolidated feedback and persist ai_summary."""
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")

    is_lead = any(p.is_lead and p.user_id == user.user_id for p in iv.panelists)
    if user.role_code not in ("HR", "ADMIN") and not is_lead:
        raise ForbiddenError("Only the lead panelist or HR/ADMIN may summarize feedback", code="RMS-E-4031")

    fb = (
        await db.execute(select(InterviewFeedback).where(InterviewFeedback.interview_id == interview_id))
    ).scalar_one_or_none()
    if fb is None:
        raise ValidationError("No consolidated feedback to summarize", code="RMS-E-4001")

    skill_ratings = [
        {"skill": r.skill.skill_name, "rating": r.rating, "remarks": r.remarks}
        for r in fb.skill_ratings
    ]
    prior = await get_prior_feedback(db, user, interview_id)  # server-injected (INV-06)
    prior_summaries = [
        {"round": p["round"], "recommendation": p["recommendation"],
         "key_points": p["ai_summary"] or {"strengths": p["strengths"], "concerns": p["weaknesses"]}}
        for p in prior
    ]

    result = await feedback_summarization.run(
        interview_id=interview_id,
        round=iv.round,
        overall_rating=float(fb.overall_rating),
        recommendation=fb.recommendation,
        skill_ratings=skill_ratings,
        attributes=fb.attributes or {},
        raw_notes=fb.raw_notes,
        prior_round_summaries=prior_summaries,
        triggered_by=user.user_id,
    )
    fb.ai_summary = result
    await audit_service.record(
        db, entity_type="INTERVIEW", entity_id=str(interview_id), action="FEEDBACK_SUMMARIZED",
        performed_by=user.user_id,
        after_state={"final_recommendation_echo": result.get("final_recommendation_echo")},
    )
    await db.commit()
    return {"interview_id": str(interview_id), "feedback_id": str(fb.feedback_id), "ai_summary": result}


async def get_feedback(db: AsyncSession, user: User, interview_id: uuid.UUID) -> dict | None:
    """Read the consolidated feedback for THIS interview. Visible to the interview's own
    panelists and to HR/ADMIN. Returns None if none has been submitted yet."""
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")

    is_panelist = any(p.user_id == user.user_id for p in iv.panelists)
    if user.role_code not in ("HR", "ADMIN") and not is_panelist:
        raise ForbiddenError("Not permitted to view feedback for this interview", code="RMS-E-4031")

    fb = (
        await db.execute(select(InterviewFeedback).where(InterviewFeedback.interview_id == interview_id))
    ).scalar_one_or_none()
    if fb is None:
        return None
    return _feedback_out(fb, iv.status)


async def get_prior_feedback(db: AsyncSession, user: User, interview_id: uuid.UUID) -> list[dict]:
    """INV-06: interviewer of round N sees consolidated feedback of rounds < N for the same
    application only. Server injects it — the requester never supplies prior data."""
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")

    is_panelist = any(p.user_id == user.user_id for p in iv.panelists)
    if user.role_code not in ("HR", "ADMIN") and not is_panelist:
        raise ForbiddenError("Not permitted to view prior feedback for this interview", code="RMS-E-4031")

    return await _prior_round_feedback(db, iv)


async def _prior_round_feedback(db: AsyncSession, iv: Interview) -> list[dict]:
    """Consolidated feedback of earlier rounds of the same application (no access gate — callers
    that reach here have already been authorized)."""
    current_ord = _ROUND_ORDER.get(iv.round, 1)
    prior_rounds = [r for r, o in _ROUND_ORDER.items() if o < current_ord]
    if not prior_rounds:
        return []

    rows = (
        await db.execute(
            select(
                Interview.round, InterviewFeedback.overall_rating, InterviewFeedback.recommendation,
                InterviewFeedback.strengths, InterviewFeedback.weaknesses,
                InterviewFeedback.attributes, InterviewFeedback.ai_summary,
            )
            .join(InterviewFeedback, InterviewFeedback.interview_id == Interview.interview_id)
            .where(Interview.application_id == iv.application_id, Interview.round.in_(prior_rounds))
            .order_by(Interview.scheduled_start)
        )
    ).all()
    return [
        {"round": r[0], "overall_rating": float(r[1]), "recommendation": r[2],
         "strengths": r[3], "weaknesses": r[4],
         "assessments": _assessments_of(r[5]), "ai_summary": r[6]}
        for r in rows
    ]


# =========================================================================== #
# SUGGESTED INTERVIEW QUESTIONS (AGENT-6)                                      #
# =========================================================================== #
def _can_view_interview(user: User, app: Application, iv: Interview) -> bool:
    """View access: ADMIN/HR; the HM who owns the RRF; any assigned panelist (INTERVIEWER)."""
    if user.role_code in ("ADMIN", "HR"):
        return True
    if user.role_code == "HIRING_MANAGER":
        return app.rrf.created_by == user.user_id
    return any(p.user_id == user.user_id for p in iv.panelists)


def _detail_out(iv: Interview, app: Application, cand: Candidate) -> dict:
    """Interview + the candidate/role context the detail screen needs, plus cached questions."""
    return {
        **serialize(iv),
        "candidate": {
            "candidate_id": str(cand.candidate_id),
            "full_name": cand.full_name,
            "email": cand.email,
            "phone": cand.phone,
            "total_experience_years": float(cand.total_experience_years)
            if cand.total_experience_years is not None else None,
            "current_company": cand.current_company,
        },
        "position_title": app.rrf.position_title,
        "min_experience_years": float(app.rrf.min_experience_years),
        "ai_screen_score": float(app.ai_screen_score) if app.ai_screen_score is not None else None,
        "ai_interview_questions": iv.ai_interview_questions,
    }


async def get_interview_detail(db: AsyncSession, user: User, interview_id: uuid.UUID) -> dict:
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")
    app = await application_repo.get_by_id(db, iv.application_id)
    if app is None:
        raise NotFoundError("Application not found", code="RMS-E-4041")
    if not _can_view_interview(user, app, iv):
        raise ForbiddenError("Not permitted to view this interview", code="RMS-E-4031")
    return _detail_out(iv, app, app.candidate)


async def get_questions(db: AsyncSession, user: User, interview_id: uuid.UUID) -> dict | None:
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")
    app = await application_repo.get_by_id(db, iv.application_id)
    if app is None:
        raise NotFoundError("Application not found", code="RMS-E-4041")
    if not _can_view_interview(user, app, iv):
        raise ForbiddenError("Not permitted to view this interview", code="RMS-E-4031")
    return iv.ai_interview_questions


async def generate_questions_bg(interview_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Pre-generate the suggested question set right after an interview is scheduled.

    Fire-and-forget (spawned from the router), opens its own DB session, and never raises —
    an AI failure must not affect the already-committed interview. Skips if a set is already
    cached, so re-scheduling never clobbers questions a user may have already re-generated.
    A user can still get a fresh set at any time via the manual 'Re-generate' action."""
    if not settings.AUTO_GENERATE_QUESTIONS or settings.APP_ENV == "test":
        return
    try:
        async with SessionLocal() as db:
            iv = await interview_repo.get_by_id(db, interview_id)
            if iv is None or iv.ai_interview_questions is not None:
                return
            user = await user_repo.get_by_id(db, user_id)
            if user is None:
                return
            await generate_questions(db, user, interview_id)
    except Exception as exc:  # noqa: BLE001 — best-effort; log and move on
        _log.warning("auto-generate questions failed for %s: %s", interview_id, exc)


async def generate_questions(db: AsyncSession, user: User, interview_id: uuid.UUID) -> dict:
    """AGENT-6: generate suggested interview questions from the CV + JD + round, cache on the
    interview. HR/ADMIN or the RRF-owning HM only (interviewers view but do not generate)."""
    iv = await interview_repo.get_by_id(db, interview_id)
    if iv is None:
        raise NotFoundError("Interview not found", code="RMS-E-4041")
    app = await application_repo.get_by_id(db, iv.application_id)
    if app is None:
        raise NotFoundError("Application not found", code="RMS-E-4041")

    if user.role_code == "HIRING_MANAGER" and app.rrf.created_by != user.user_id:
        raise ForbiddenError("Not permitted to generate questions for this interview", code="RMS-E-4031")

    rrf, cand = app.rrf, app.candidate
    essential = [f"{s.skill.skill_name} (priority {s.priority})"
                 for s in rrf.skills if s.req_type == "ESSENTIAL"]
    desired = [s.skill.skill_name for s in rrf.skills if s.req_type == "DESIRED"]

    # Reuse the JD resolution used by resume screening (latest JD version, else RRF fallback).
    from app.services.pipeline_service import _fallback_jd, _latest_jd_markdown
    jd = await _latest_jd_markdown(db, rrf.rrf_id) or _fallback_jd(rrf)

    # Server-injected prior-round focus (INV-06): concerns + suggested next-round focus.
    # Use the ungated helper — the generating user (HR/ADMIN or RRF-owning HM) is already
    # authorized above and may not be on this interview's panel.
    prior = await _prior_round_feedback(db, iv)
    prior_focus: list[str] = []
    for p in prior:
        if p.get("weaknesses"):
            prior_focus.append(str(p["weaknesses"]))
        nxt = (p.get("ai_summary") or {}).get("suggested_focus_next_round") if isinstance(p.get("ai_summary"), dict) else None
        if isinstance(nxt, list):
            prior_focus.extend(str(x) for x in nxt)

    result = await interview_questions.run(
        interview_id=interview_id,
        round=iv.round,
        position_title=rrf.position_title,
        min_experience_years=float(rrf.min_experience_years),
        jd_markdown=jd,
        essential_skills=essential,
        desired_skills=desired,
        cv_text=cand.cv_text or "",
        candidate_experience_years=float(cand.total_experience_years)
        if cand.total_experience_years is not None else None,
        prior_round_focus=prior_focus,
        triggered_by=user.user_id,
    )

    iv.ai_interview_questions = result
    await audit_service.record(
        db, entity_type="INTERVIEW", entity_id=str(interview_id), action="QUESTIONS_GENERATED",
        performed_by=user.user_id,
        after_state={"round": iv.round, "question_count": len(result.get("questions") or [])},
    )
    # Build the response BEFORE commit — commit expires all ORM attributes, and touching
    # iv/app/cand afterwards would fire an async lazy-load (MissingGreenlet). See submit_feedback.
    detail = _detail_out(iv, app, cand)
    await db.commit()
    return detail
