"""/offers router — draft, fixed-template letter (INV-10), release/accept/decline/withdraw."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_roles
from app.models.user import User
from app.schemas.offer import OfferCreate, OfferTransition, OfferUpdate
from app.services import offer_service

router = APIRouter(prefix="/offers", tags=["offers"])

_ROLES = ("ADMIN", "HR")


@router.get("")
async def list_offers(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*_ROLES, "HIRING_MANAGER")),
) -> dict:
    return {"success": True, "data": await offer_service.list_offers(db)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_offer(
    payload: OfferCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ROLES)),
) -> dict:
    data = await offer_service.create_offer(db, user, payload)
    return {"success": True, "data": data}


@router.patch("/{offer_id}")
async def update_offer(
    offer_id: uuid.UUID,
    payload: OfferUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ROLES)),
) -> dict:
    data = await offer_service.update_offer(db, user, offer_id, payload)
    return {"success": True, "data": data}


@router.post("/{offer_id}/generate-letter")
async def generate_letter(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ROLES)),
) -> dict:
    data = await offer_service.generate_letter(db, user, offer_id)
    return {"success": True, "data": data}


@router.post("/{offer_id}/transition")
async def transition_offer(
    offer_id: uuid.UUID,
    payload: OfferTransition,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ROLES)),
) -> dict:
    data = await offer_service.transition(db, user, offer_id, payload.action, payload.comment)
    return {"success": True, "data": data}


@router.get("/{offer_id}")
async def get_offer(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*_ROLES, "HIRING_MANAGER")),
) -> dict:
    data = await offer_service.get_offer(db, user, offer_id)
    return {"success": True, "data": data}
