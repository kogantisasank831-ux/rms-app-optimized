"""/careers router — public job feed + candidate self-service (signup, apply, my portal).

Public:            GET /careers/jobs, POST /careers/signup
Candidate (JWT):   POST /careers/apply, GET /careers/me
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_roles
from app.models.user import User
from app.services import careers_service

router = APIRouter(prefix="/careers", tags=["careers"])


@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db)) -> dict:
    return {"success": True, "data": await careers_service.list_jobs(db)}


@router.get("/jobs/{job_code}")
async def get_job(job_code: str, db: AsyncSession = Depends(get_db)) -> dict:
    return {"success": True, "data": await careers_service.get_job(db, job_code)}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str | None = Form(default=None),
    cv_file: UploadFile = File(...),
    photo: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await cv_file.read()
    photo_data = await photo.read() if photo is not None else None
    result = await careers_service.signup(
        db, full_name=full_name, email=email, password=password, phone=phone,
        filename=cv_file.filename or "cv", content_type=cv_file.content_type or "", data=data,
        photo_data=photo_data or None,
        photo_content_type=photo.content_type if photo is not None else None,
    )
    return {"success": True, "data": result}


class ApplyBody(BaseModel):
    rrf_id: str


@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def apply(
    body: ApplyBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("CANDIDATE")),
) -> dict:
    return {"success": True, "data": await careers_service.apply(db, user, body.rrf_id)}


@router.get("/me")
async def my_portal(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("CANDIDATE")),
) -> dict:
    return {"success": True, "data": await careers_service.my_portal(db, user)}


class OfferRespondBody(BaseModel):
    action: str  # ACCEPT | DECLINE
    comment: str | None = None  # candidate's reason (optional)


@router.post("/offers/{offer_id}/respond")
async def respond_offer(
    offer_id: str,
    body: OfferRespondBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("CANDIDATE")),
) -> dict:
    return {"success": True, "data": await careers_service.respond_offer(db, user, offer_id, body.action, body.comment)}
