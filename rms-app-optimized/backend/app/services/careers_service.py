"""careers_service — public career portal + candidate self-service.

Candidates sign up as CANDIDATE users (reusing the JWT/auth plumbing) and get a linked
candidate profile (with CV). Applying from the portal flows into the real ATS pipeline
(pipeline_service.create_application), so HR sees the application and agents screen it.
"""
from __future__ import annotations

import datetime
import re
import uuid

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import create_access_token, get_password_hash
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.offer import Offer
from app.models.rrf import RRF
from app.models.user import Role, User
from app.repositories import application_repo, candidate_repo, offer_repo, user_repo
from app.services import (
    audit_service,
    avatar_service,
    offer_service,
    pipeline_service,
    storage_service,
)
from app.utils.cv_text_extract import extract_text

_ALLOWED_EXT = {"pdf", "docx"}
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_DUMMY_MEETING = "https://teams.microsoft.com/l/meetup-join/dataalchemists-ats-demo"


# --------------------------------------------------------------------------- signup / auth
async def signup(
    db: AsyncSession, *, full_name: str, email: str, password: str,
    phone: str | None, filename: str, content_type: str, data: bytes,
    photo_data: bytes | None = None, photo_content_type: str | None = None,
) -> dict:
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    if not full_name or not email or not password:
        raise ValidationError("Name, email and password are required", code="RMS-E-4001")
    if len(password) < 6:
        raise ValidationError("Password must be at least 6 characters", code="RMS-E-4001")

    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in _ALLOWED_EXT:
        raise ValidationError("Resume must be a .pdf or .docx file", code="RMS-E-4001")
    if not data:
        raise ValidationError("Resume file is empty", code="RMS-E-4001")

    if await user_repo.get_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists — please sign in.", code="RMS-E-4091")
    if await candidate_repo.get_by_email(db, email) is not None:
        raise ConflictError("This email is already registered — please sign in.", code="RMS-E-4091")

    phone_digits = re.sub(r"\D", "", phone or "")
    if phone_digits and await candidate_repo.get_by_phone(db, phone_digits) is not None:
        raise ConflictError("This phone number is already registered — please sign in.", code="RMS-E-4091")

    role = (await db.execute(select(Role).where(Role.role_code == "CANDIDATE"))).scalar_one_or_none()
    if role is None:
        raise ValidationError("Candidate role is not configured", code="RMS-E-4001")

    now = datetime.datetime.now(datetime.timezone.utc)
    user = User(
        user_id=uuid.uuid4(), email=email, password_hash=get_password_hash(password),
        full_name=full_name, role_id=role.role_id, designation="Applicant",
        is_active=True, created_at=now, updated_at=now,
    )
    db.add(user)
    await db.flush()

    candidate_id = uuid.uuid4()
    safe = _SAFE.sub("_", filename).strip("_") or "cv"
    key = f"{storage_service.CV_PREFIX}{now.year}/{now.month:02d}/{candidate_id}_{safe}"
    cv_text = await run_in_threadpool(extract_text, filename, data)
    await storage_service.put_object(
        key, data, content_type or "application/octet-stream",
        metadata={"entity-type": "CANDIDATE", "entity-id": str(candidate_id), "uploaded-by": str(user.user_id)},
    )
    candidate = Candidate(
        candidate_id=candidate_id, full_name=full_name, email=email, phone=phone,
        source="CAREER_PORTAL", cv_object_key=key, cv_file_name=filename,
        cv_text=cv_text or None, created_by=user.user_id,
    )
    db.add(candidate)
    await db.flush()

    # Optional profile photo: render icon + profile WebP once, store on both the user and
    # the candidate rows so the person shows the same avatar across the app and the portal.
    photo_icon_key = photo_object_key = None
    if photo_data:
        photo_icon_key, photo_object_key = await avatar_service.process_and_store(
            owner_type="candidates", owner_id=candidate_id,
            data=photo_data, content_type=photo_content_type or "",
        )
        user.photo_icon_key = candidate.photo_icon_key = photo_icon_key
        user.photo_object_key = candidate.photo_object_key = photo_object_key
        await db.flush()

    await audit_service.record(
        db, entity_type="CANDIDATE", entity_id=str(candidate_id), action="SELF_SIGNUP",
        performed_by=user.user_id, after_state={"email": email, "source": "CAREER_PORTAL"},
    )
    await db.commit()

    token, expires_in = create_access_token(user.user_id, "CANDIDATE")
    return {
        "access_token": token, "token_type": "bearer", "expires_in": expires_in,
        "user": {"user_id": str(user.user_id), "full_name": full_name, "email": email,
                 "role": "CANDIDATE", "designation": "Applicant",
                 **await avatar_service.urls(photo_icon_key, photo_object_key)},
    }


# --------------------------------------------------------------------------- jobs (public)
def _job(rrf: RRF) -> dict:
    tags = sorted({s.skill.skill_name for s in rrf.skills}) if rrf.skills else []
    return {
        "rrf_id": str(rrf.rrf_id),
        "job_code": rrf.job_code,  # PUBLIC job id; internal rrf_code is intentionally not exposed
        "title": rrf.position_title,
        "department": rrf.business_unit.bu_name if rrf.business_unit else None,
        "project_name": rrf.project_name,
        "location": rrf.assignment_location,
        "wfh_allowed": rrf.wfh_allowed,
        "min_experience_years": float(rrf.min_experience_years) if rrf.min_experience_years is not None else 0.0,
        "employment_type": "Full-time",
        "needed_by_date": rrf.needed_by_date.isoformat() if rrf.needed_by_date else None,
        "posted_at": rrf.created_at.isoformat() if rrf.created_at else None,
        "openings": rrf.positions_count,
        "tags": tags,
        "blurb": (rrf.scope_of_work or "").strip()[:280] or None,
        "salary_range": rrf.salary_range,
    }


def _job_detail(rrf: RRF) -> dict:
    """Full public job page: the card fields plus skills (split essential/desired),
    the job description, responsibilities and eligibility."""
    essential = sorted({s.skill.skill_name for s in rrf.skills if s.req_type == "ESSENTIAL"}) if rrf.skills else []
    desired = sorted({s.skill.skill_name for s in rrf.skills if s.req_type == "DESIRED"}) if rrf.skills else []
    responsibilities = [
        line.strip("-• \t") for line in (rrf.responsibilities or "").splitlines() if line.strip()
    ]
    return {
        **_job(rrf),
        "base_location": rrf.base_location,
        "shift_hours": rrf.shift_hours,
        "education_qualification": rrf.education_qualification,
        # Public JD description is the AI-generated / editable scope of work only.
        # Never fall back to `justification` — that is HR's internal business reason
        # for the requisition and must not be shown on the public careers portal.
        "description": (rrf.scope_of_work or "").strip() or None,
        "responsibilities": responsibilities,
        "essential_skills": essential,   # required
        "desired_skills": desired,       # optional / nice-to-have
    }


async def list_jobs(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(select(RRF).where(RRF.status == "APPROVED").order_by(RRF.created_at.desc()))
    ).unique().scalars().all()
    return [_job(r) for r in rows]


async def get_job(db: AsyncSession, job_code: str) -> dict:
    """Public detail for a single open role, keyed by the public job code."""
    rrf = (
        await db.execute(select(RRF).where(RRF.job_code == job_code, RRF.status == "APPROVED"))
    ).unique().scalar_one_or_none()
    if rrf is None:
        raise NotFoundError("This role is not open, or the link is no longer valid.", code="RMS-E-4041")
    return _job_detail(rrf)


# --------------------------------------------------------------------------- apply
async def _my_candidate(db: AsyncSession, user: User) -> Candidate:
    c = await candidate_repo.get_by_email(db, user.email)
    if c is None:
        raise NotFoundError("No candidate profile is linked to this account.", code="RMS-E-4041")
    return c


async def apply(db: AsyncSession, user: User, rrf_id: str) -> dict:
    candidate = await _my_candidate(db, user)
    # Reuse the real pipeline intake (RRF must be APPROVED, dedupe, auto-screen).
    return await pipeline_service.create_application(db, user, rrf_id, str(candidate.candidate_id))


# --------------------------------------------------------------------------- respond to offer
async def respond_offer(db: AsyncSession, user: User, offer_id: str, action: str, comment: str | None = None) -> dict:
    """Candidate accepts or declines their OWN released offer from the portal.

    Reuses the offer state machine (offer_service.transition) so the application pipeline is
    driven identically to an HR-initiated response (G11 accept / G13 decline), with audit +
    offer_status_history rows and HR notification. Ownership is enforced here (row-scope).
    """
    action = (action or "").strip().upper()
    if action not in ("ACCEPT", "DECLINE"):
        raise ValidationError("Action must be ACCEPT or DECLINE", code="RMS-E-4001")
    try:
        oid = uuid.UUID(offer_id)
    except ValueError as exc:
        raise ValidationError("invalid offer_id", code="RMS-E-4001") from exc

    offer = await offer_repo.get_by_id(db, oid)
    if offer is None:
        raise NotFoundError("Offer not found", code="RMS-E-4041")

    # Row-scope: the offer's application must belong to the signed-in candidate.
    candidate = await _my_candidate(db, user)
    app = await application_repo.get_by_id(db, offer.application_id)
    if app is None or app.candidate_id != candidate.candidate_id:
        raise ForbiddenError("This offer is not associated with your account.", code="RMS-E-4031")

    default = (
        "Candidate accepted the offer via the careers portal."
        if action == "ACCEPT"
        else "Candidate declined the offer via the careers portal."
    )
    reason = (comment or "").strip()
    # INV-01: transitions require a non-empty comment; use the candidate's reason
    # when supplied, otherwise fall back to a descriptive default.
    final = f"{default} Reason: {reason}" if reason else default
    return await offer_service.transition(db, user, oid, action, final)


# --------------------------------------------------------------------------- my portal
async def _offer_view(db: AsyncSession, application_id: uuid.UUID) -> dict | None:
    offer = (
        await db.execute(select(Offer).where(Offer.application_id == application_id))
    ).scalar_one_or_none()
    if offer is None:
        return None
    letter_url = None
    if offer.letter_object_key and offer.status in ("RELEASED", "ACCEPTED"):
        letter_url = await storage_service.presigned_get_url(offer.letter_object_key, ensure_exists=False)
    return {
        "offer_id": str(offer.offer_id),
        "offer_code": offer.offer_code,
        "status": offer.status,
        "designation": offer.designation,
        "ctc_annual": offer.ctc_annual,
        "work_location": offer.work_location,
        "joining_date": offer.joining_date.isoformat() if offer.joining_date else None,
        "valid_until": offer.valid_until.isoformat() if offer.valid_until else None,
        "letter_url": letter_url,
    }


async def _interviews_view(db: AsyncSession, application_id: uuid.UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(Interview)
            .where(Interview.application_id == application_id, Interview.status == "SCHEDULED")
            .order_by(Interview.scheduled_start)
        )
    ).unique().scalars().all()
    out = []
    for iv in rows:
        out.append({
            "interview_id": str(iv.interview_id),
            "round": iv.round,
            "mode": iv.mode,
            "scheduled_start": iv.scheduled_start.isoformat() if iv.scheduled_start else None,
            "scheduled_end": iv.scheduled_end.isoformat() if iv.scheduled_end else None,
            "location": iv.location,
            "join_link": iv.meeting_link or (_DUMMY_MEETING if iv.mode != "IN_PERSON" else None),
        })
    return out


async def my_portal(db: AsyncSession, user: User) -> dict:
    candidate = await candidate_repo.get_by_email(db, user.email)
    profile = {
        "full_name": user.full_name, "email": user.email,
        "candidate_id": str(candidate.candidate_id) if candidate else None,
        **await avatar_service.urls(user.photo_icon_key, user.photo_object_key),
    }
    if candidate is None:
        return {"profile": profile, "applications": []}

    apps = (
        await db.execute(
            select(Application)
            .where(Application.candidate_id == candidate.candidate_id)
            .order_by(Application.created_at.desc())
        )
    ).unique().scalars().all()

    applications = []
    for app in apps:
        applications.append({
            "application_id": str(app.application_id),
            "rrf_id": str(app.rrf_id),
            "job_code": app.rrf.job_code,  # public job id (never expose rrf_code to candidates)
            "title": app.rrf.position_title,
            "location": app.rrf.assignment_location,
            "current_stage": app.current_stage,
            "status": app.status,
            "applied_at": app.created_at.isoformat() if app.created_at else None,
            "offer": await _offer_view(db, app.application_id),
            "interviews": await _interviews_view(db, app.application_id),
        })
    return {"profile": profile, "applications": applications}
