"""offer_service — offer draft, fixed-template letter (INV-10), state machine G16/G17.

Accept/decline drive the application pipeline (G11 -> OFFER_ACCEPTED, G13 -> REJECTED) in the
same transaction via pipeline_service system hooks.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, TransitionError, ValidationError
from app.models.offer import Offer
from app.models.user import User
from app.repositories import application_repo, offer_repo
from app.services import audit_service, notification_service, pipeline_service, storage_service
from app.utils.pdf_render import render_offer_letter

_TEMPLATE_KEY = "templates/offer_template_v1.html"

# offer state machine (LLD 4.3 / G16-G17)
OFFER_GUARD: dict[str, dict] = {
    "RELEASE": {"from": {"DRAFT"}, "to": "RELEASED"},          # requires generated letter (INV-10)
    "ACCEPT": {"from": {"RELEASED"}, "to": "ACCEPTED"},        # drives G11
    "DECLINE": {"from": {"RELEASED"}, "to": "DECLINED"},       # drives G13
    "WITHDRAW": {"from": {"DRAFT", "RELEASED"}, "to": "WITHDRAWN"},
}


def _ordinal(day: int) -> str:
    """1 -> 1st, 2 -> 2nd, 13 -> 13th ... (letter-style dates)."""
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _long_date(d: datetime.date | None) -> str:
    """e.g. 2022-05-13 -> 'May 13th, 2022'. Empty string for None."""
    if d is None:
        return ""
    return f"{d.strftime('%B')} {_ordinal(d.day)}, {d.year}"


def serialize(o: Offer) -> dict:
    return {
        "offer_id": str(o.offer_id),
        "offer_code": o.offer_code,
        "application_id": str(o.application_id),
        "candidate_name": o.candidate_name,
        "designation": o.designation,
        "ctc_annual": o.ctc_annual,
        "monthly_gross": o.monthly_gross,
        "joining_date": o.joining_date,
        "work_location": o.work_location,
        "status": o.status,
        "valid_until": o.valid_until,
        "letter_object_key": o.letter_object_key,
        "created_at": o.created_at,
    }


async def list_offers(db: AsyncSession) -> list[dict]:
    """Lightweight list keyed by application_id — used by the Offers console to show each
    application's offer status (Draft / Shared / Accepted / Declined)."""
    rows = await offer_repo.list_all(db)
    return [
        {
            "offer_id": str(o.offer_id),
            "application_id": str(o.application_id),
            "offer_code": o.offer_code,
            "status": o.status,
            "letter_ready": bool(o.letter_object_key),
        }
        for o in rows
    ]


async def create_offer(db: AsyncSession, user: User, payload) -> dict:
    try:
        app_id = uuid.UUID(payload.application_id)
    except ValueError as exc:
        raise ValidationError("invalid application_id", code="RMS-E-4001") from exc

    app = await application_repo.get_by_id(db, app_id)
    if app is None:
        raise ValidationError("Application not found", code="RMS-E-4001")
    if app.status != "ACTIVE":
        raise ValidationError("Application must be active to create an offer", code="RMS-E-4001")
    if await offer_repo.get_by_application(db, app_id) is not None:
        raise ConflictError("An offer already exists for this application", code="RMS-E-4091")

    # Creating an offer moves the candidate into the OFFER stage (kanban updates). Eligible from
    # the shortlist or any interview round — validated + audited inside system_move_to_offer.
    await pipeline_service.system_move_to_offer(
        db, user, app, f"Moved to OFFER on offer creation ({user.full_name})"
    )

    year = datetime.datetime.now(datetime.timezone.utc).year
    code = await offer_repo.next_offer_code(db, year)
    default_name = app.candidate.full_name if app.candidate else None
    offer = Offer(
        application_id=app_id, offer_code=code,
        candidate_name=(payload.candidate_name or "").strip() or default_name,
        designation=payload.designation,
        ctc_annual=payload.ctc_annual, monthly_gross=(payload.monthly_gross or "").strip() or None,
        joining_date=payload.joining_date,
        work_location=payload.work_location, valid_until=payload.valid_until,
        status="DRAFT", generated_by=user.user_id,
    )
    db.add(offer)
    await db.flush()
    await audit_service.record(
        db, entity_type="OFFER", entity_id=str(offer.offer_id), action="CREATE",
        performed_by=user.user_id, after_state={"offer_code": code, "status": "DRAFT"},
    )
    await db.commit()
    await db.refresh(offer)
    return serialize(offer)


async def update_offer(db: AsyncSession, user: User, offer_id: uuid.UUID, payload) -> dict:
    """Edit a DRAFT offer's terms before the letter is generated/released. DRAFT-only."""
    offer = await offer_repo.get_by_id(db, offer_id)
    if offer is None:
        raise NotFoundError("Offer not found", code="RMS-E-4041")
    if offer.status != "DRAFT":
        raise TransitionError("Only a DRAFT offer can be edited", code="RMS-E-4221")

    before = serialize(offer)
    fields = payload.model_dump(exclude_unset=True)
    for key in ("candidate_name", "designation", "ctc_annual", "monthly_gross",
                "joining_date", "work_location", "valid_until"):
        if key in fields and fields[key] is not None:
            value = fields[key]
            if isinstance(value, str):
                value = value.strip() or None
            setattr(offer, key, value)
    # Editing terms invalidates any previously generated letter — force a regenerate before release.
    offer.letter_object_key = None
    await audit_service.record(
        db, entity_type="OFFER", entity_id=str(offer_id), action="UPDATE",
        performed_by=user.user_id, before_state=before, after_state=serialize(offer),
    )
    await db.commit()
    await db.refresh(offer)
    return serialize(offer)


async def generate_letter(db: AsyncSession, user: User, offer_id: uuid.UUID) -> dict:
    """INV-10: fill the FIXED template, render (PDF or HTML fallback), store in MinIO."""
    offer = await offer_repo.get_by_id(db, offer_id)
    if offer is None:
        raise NotFoundError("Offer not found", code="RMS-E-4041")
    app = await application_repo.get_by_id(db, offer.application_id)
    default_name = app.candidate.full_name if app and app.candidate else "Candidate"
    candidate_name = offer.candidate_name or default_name
    # Salutation uses the first name (e.g. "Dear Deepankar,").
    first_name = candidate_name.split()[0] if candidate_name else candidate_name

    template_html = (await storage_service.get_object(_TEMPLATE_KEY)).decode("utf-8")
    variables = {
        "candidate_name": candidate_name,
        "first_name": first_name,
        "designation": offer.designation,
        "ctc_annual": offer.ctc_annual,           # Total Cost to Company
        "monthly_gross": offer.monthly_gross or "—",
        "joining_date": _long_date(offer.joining_date),
        "work_location": offer.work_location,
        "offer_code": offer.offer_code,
        "valid_until": _long_date(offer.valid_until) if offer.valid_until else "N/A",
        "hr_name": user.full_name,
        "issue_date": _long_date(datetime.datetime.now(datetime.timezone.utc).date()),
    }
    data, content_type, ext = render_offer_letter(template_html, variables)
    year = offer.created_at.year if offer.created_at else datetime.datetime.now(datetime.timezone.utc).year
    key = f"{storage_service.OFFER_PREFIX}{year}/{offer.offer_code}.{ext}"
    await storage_service.put_object(key, data, content_type,
                                     metadata={"entity-type": "OFFER", "entity-id": str(offer_id)})

    offer.letter_object_key = key
    await audit_service.record(
        db, entity_type="OFFER", entity_id=str(offer_id), action="GENERATE_LETTER",
        performed_by=user.user_id, after_state={"letter_object_key": key, "format": ext},
    )
    await db.commit()

    url = await storage_service.presigned_get_url(key)
    return {"letter_object_key": key, "download_url": url, "template_version": "v1-fixed"}


async def _write_history(db, offer_id, from_status, to_status, comment, changed_by) -> None:
    await db.execute(
        text(
            "INSERT INTO offer_status_history (offer_id, from_status, to_status, comment, changed_by) "
            "VALUES (:oid, CAST(:fs AS offer_status), CAST(:ts AS offer_status), :c, :by)"
        ),
        {"oid": str(offer_id), "fs": from_status, "ts": to_status, "c": comment, "by": str(changed_by)},
    )


async def transition(db: AsyncSession, user: User, offer_id: uuid.UUID, action: str, comment: str) -> dict:
    action = (action or "").upper()
    if not comment or not comment.strip():
        raise TransitionError("A non-empty comment is required for every transition", code="RMS-E-4222")
    rule = OFFER_GUARD.get(action)
    if rule is None:
        raise TransitionError(f"Unknown action '{action}'", code="RMS-E-4221")

    offer = await offer_repo.get_by_id(db, offer_id)
    if offer is None:
        raise NotFoundError("Offer not found", code="RMS-E-4041")
    from_status = offer.status
    if from_status not in rule["from"]:
        raise TransitionError(f"Transition {from_status}->{action} not permitted", code="RMS-E-4221")

    if action == "RELEASE" and not offer.letter_object_key:
        raise TransitionError("Generate the offer letter before releasing (INV-10)", code="RMS-E-4221")

    to_status = rule["to"]
    offer.status = to_status
    if action == "RELEASE":
        offer.released_at = func.now()
    if action in ("ACCEPT", "DECLINE"):
        offer.responded_at = func.now()

    # drive the application pipeline (same transaction)
    if action == "ACCEPT":
        await pipeline_service.system_offer_accepted(db, user, offer.application_id, comment)
    elif action == "DECLINE":
        await pipeline_service.system_offer_declined(db, user, offer.application_id, comment)

    await _write_history(db, offer_id, from_status, to_status, comment, user.user_id)
    await audit_service.record(
        db, entity_type="OFFER", entity_id=str(offer_id), action=f"TRANSITION:{action}",
        performed_by=user.user_id, before_state={"status": from_status},
        after_state={"status": to_status, "comment": comment},
    )
    app = await application_repo.get_by_id(db, offer.application_id)
    if app is not None and app.rrf.created_by != user.user_id:
        await notification_service.notify(
            db, user_id=app.rrf.created_by, title=f"Offer {offer.offer_code}: {action}",
            body=comment, link_path=f"/offers/{offer_id}",
        )
    await db.commit()
    return {"offer_id": str(offer_id), "from_status": from_status, "status": to_status, "action": action}


async def get_offer(db: AsyncSession, user: User, offer_id: uuid.UUID) -> dict:
    offer = await offer_repo.get_by_id(db, offer_id)
    if offer is None:
        raise NotFoundError("Offer not found", code="RMS-E-4041")
    return serialize(offer)

