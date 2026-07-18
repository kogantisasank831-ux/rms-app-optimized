"""/interviews router — schedule (panel 1..5), my-interviews, list-by-application, cancel/no-show/reschedule.

Slot suggestion (T-302), prior-feedback + feedback (T-303) are added in later tasks.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.schemas.feedback import FeedbackCreate
from app.schemas.interview import InterviewCreate, InterviewPatch
from app.schemas.scheduling import SuggestSlotsRequest
from app.services import interview_service

router = APIRouter(prefix="/interviews", tags=["interviews"])
_log = logging.getLogger("rms.interviews")

_SCHEDULE_ROLES = ("ADMIN", "HR")
_READ_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")
# feedback + prior-feedback: lead panelist / interviewers are gated inside the service (INV-06)
_FEEDBACK_ROLES = ("ADMIN", "HR", "HIRING_MANAGER", "INTERVIEWER")
# suggested questions: HR/HM generate (HM ownership checked in service); panel can also view
_QUESTIONS_GEN_ROLES = ("ADMIN", "HR", "HIRING_MANAGER")
_QUESTIONS_VIEW_ROLES = ("ADMIN", "HR", "HIRING_MANAGER", "INTERVIEWER")


@router.post("", status_code=status.HTTP_201_CREATED)
async def schedule_interview(
    payload: InterviewCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_SCHEDULE_ROLES)),
) -> dict:
    data = await interview_service.schedule(db, user, payload)
    # Pre-generate the AI question set in the background so it's ready by the time the panel
    # opens the interview. Detached like the feedback summary — never blocks the response.
    _spawn_questions(uuid.UUID(data["interview_id"]), user.user_id)
    return {"success": True, "data": data}


@router.post("/suggest-slots")
async def suggest_slots(
    payload: SuggestSlotsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_SCHEDULE_ROLES)),
) -> dict:
    data = await interview_service.suggest_slots(db, user, payload)
    return {"success": True, "data": data}


# NOTE: /my must be declared before /{interview_id} so it is not captured as an id
@router.get("/my")
async def my_interviews(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    data = await interview_service.list_my(db, user)
    return {"success": True, "data": data}


@router.get("/{interview_id}")
async def get_interview(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_QUESTIONS_VIEW_ROLES)),
) -> dict:
    data = await interview_service.get_interview_detail(db, user, interview_id)
    return {"success": True, "data": data}


@router.get("/{interview_id}/questions")
async def get_questions(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_QUESTIONS_VIEW_ROLES)),
) -> dict:
    data = await interview_service.get_questions(db, user, interview_id)
    return {"success": True, "data": data}


@router.post("/{interview_id}/questions", status_code=status.HTTP_201_CREATED)
async def generate_questions(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_QUESTIONS_GEN_ROLES)),
) -> dict:
    data = await interview_service.generate_questions(db, user, interview_id)
    return {"success": True, "data": data}


@router.get("")
async def list_interviews(
    application_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_READ_ROLES)),
) -> dict:
    data = await interview_service.list_by_application(db, user, application_id)
    return {"success": True, "data": data}


@router.patch("/{interview_id}")
async def patch_interview(
    interview_id: uuid.UUID,
    payload: InterviewPatch,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_SCHEDULE_ROLES)),
) -> dict:
    data = await interview_service.patch(db, user, interview_id, payload)
    return {"success": True, "data": data}


@router.get("/{interview_id}/feedback")
async def get_feedback(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_FEEDBACK_ROLES)),
) -> dict:
    data = await interview_service.get_feedback(db, user, interview_id)
    return {"success": True, "data": data}


@router.get("/{interview_id}/prior-feedback")
async def prior_feedback(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_FEEDBACK_ROLES)),
) -> dict:
    data = await interview_service.get_prior_feedback(db, user, interview_id)
    return {"success": True, "data": data}


@router.post("/{interview_id}/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    interview_id: uuid.UUID,
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_FEEDBACK_ROLES)),
) -> dict:
    data = await interview_service.submit_feedback(db, user, interview_id, payload)
    # AGENT-5 summary is fully detached from this request via asyncio.create_task — NOT a
    # FastAPI BackgroundTask, which would hold the HTTP connection open for the ~30s Claude
    # call and stall the client's follow-up refetch on the same keep-alive connection.
    _spawn_summary(interview_id, user.user_id)
    return {"success": True, "data": data}


# Keep strong references so fire-and-forget tasks aren't garbage-collected mid-flight.
_bg_tasks: set[asyncio.Task] = set()


def _spawn_summary(interview_id: uuid.UUID, user_id: uuid.UUID) -> None:
    # Best-effort: the feedback is already committed, so scheduling the summary must never
    # turn a successful submit into a 500.
    try:
        task = asyncio.create_task(interview_service.summarize_feedback_bg(interview_id, user_id))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
    except Exception:  # noqa: BLE001
        _log.exception("failed to schedule feedback summary for %s", interview_id)


def _spawn_questions(interview_id: uuid.UUID, user_id: uuid.UUID) -> None:
    # Best-effort: the interview is already committed, so pre-generating questions must never
    # turn a successful schedule into a 500.
    try:
        task = asyncio.create_task(interview_service.generate_questions_bg(interview_id, user_id))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
    except Exception:  # noqa: BLE001
        _log.exception("failed to schedule question pre-generation for %s", interview_id)


@router.post("/{interview_id}/feedback/summarize")
async def summarize_feedback(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_FEEDBACK_ROLES)),
) -> dict:
    data = await interview_service.summarize_feedback(db, user, interview_id)
    return {"success": True, "data": data}
