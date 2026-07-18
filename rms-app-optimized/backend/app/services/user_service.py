"""user_service — directory administration (ADMIN).

Create employees who become selectable interview panelists (INV-05), and
activate/deactivate them. Every mutation writes an audit row in the same
transaction (INV-02). Business rules live here, not in the router or repo.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.security import get_password_hash
from app.models.user import User
from app.repositories import candidate_repo, user_repo
from app.services import audit_service, avatar_service

# A newly-created employee cannot be a bare CANDIDATE — the directory is for staff
# who can sit on panels or run the hiring flow.
_CREATABLE_ROLES = ("ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD", "INTERVIEWER")
DEFAULT_TEMP_PASSWORD = "Passw0rd!23"  # demo default; employee should change on first login


def _public(user: User, role_code: str, role_name: str) -> dict:
    return {
        "user_id": str(user.user_id),
        "full_name": user.full_name,
        "email": user.email,
        "role": role_code,
        "role_name": role_name,
        "designation": user.designation,
        "is_active": user.is_active,
    }


async def _public_with_photo(user: User, role_code: str, role_name: str) -> dict:
    row = _public(user, role_code, role_name)
    row.update(await avatar_service.urls(user.photo_icon_key, user.photo_object_key))
    return row


async def list_roles(db: AsyncSession) -> list[dict]:
    roles = await user_repo.list_roles(db, exclude=("CANDIDATE",))
    return [{"role_code": r.role_code, "role_name": r.role_name} for r in roles]


async def create_user(
    db: AsyncSession, *, email: str, full_name: str, role_code: str,
    designation: str | None, password: str | None, actor_id: uuid.UUID,
) -> dict:
    email = (email or "").strip()
    full_name = (full_name or "").strip()
    if not email or "@" not in email:
        raise ValidationError("A valid email is required", code="RMS-E-4001")
    if not full_name:
        raise ValidationError("Full name is required", code="RMS-E-4001")
    if role_code not in _CREATABLE_ROLES:
        raise ValidationError(
            f"Role must be one of {', '.join(_CREATABLE_ROLES)}", code="RMS-E-4001"
        )

    role = await user_repo.get_role_by_code(db, role_code)
    if role is None:
        raise ValidationError(f"Unknown role '{role_code}'", code="RMS-E-4001")
    if await user_repo.get_by_email(db, email):
        raise ConflictError(f"A user with email '{email}' already exists", code="RMS-E-4091")

    pw = password.strip() if password and password.strip() else DEFAULT_TEMP_PASSWORD
    user = await user_repo.insert(
        db, email=email, password_hash=get_password_hash(pw), full_name=full_name,
        role_id=role.role_id, designation=(designation or "").strip() or None,
    )
    result = _public(user, role.role_code, role.role_name)
    await audit_service.record(
        db, entity_type="USER", entity_id=str(user.user_id), action="CREATE",
        performed_by=actor_id, after_state=result,
    )
    await db.commit()
    return await _public_with_photo(user, role.role_code, role.role_name)


async def set_active(
    db: AsyncSession, *, user_id: uuid.UUID, is_active: bool, actor_id: uuid.UUID,
) -> dict:
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found", code="RMS-E-4041")
    before = user.is_active
    user = await user_repo.set_active(db, user, is_active)
    await audit_service.record(
        db, entity_type="USER", entity_id=str(user.user_id),
        action="ACTIVATE" if is_active else "DEACTIVATE",
        performed_by=actor_id,
        before_state={"is_active": before}, after_state={"is_active": is_active},
    )
    await db.commit()
    return await _public_with_photo(user, user.role.role_code, user.role.role_name)


async def admin_update(
    db: AsyncSession, *, user_id: uuid.UUID, actor_id: uuid.UUID,
    full_name: str | None = None, email: str | None = None,
    designation: str | None = None, role_code: str | None = None,
    is_active: bool | None = None,
) -> dict:
    """ADMIN edits a user's directory details (name / email / designation / role / status).

    Only provided fields change. Email uniqueness is enforced; role must be a real staff role.
    Writes a single audit row in the same transaction (INV-02).
    """
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found", code="RMS-E-4041")

    before = _public(user, user.role.role_code, user.role.role_name)
    role_id: int | None = None

    if full_name is not None and not full_name.strip():
        raise ValidationError("Full name cannot be empty", code="RMS-E-4001")
    if email is not None:
        email = email.strip()
        if not email or "@" not in email:
            raise ValidationError("A valid email is required", code="RMS-E-4001")
        existing = await user_repo.get_by_email(db, email)
        if existing is not None and existing.user_id != user_id:
            raise ConflictError(f"A user with email '{email}' already exists", code="RMS-E-4091")
    if role_code is not None:
        if role_code not in _CREATABLE_ROLES:
            raise ValidationError(
                f"Role must be one of {', '.join(_CREATABLE_ROLES)}", code="RMS-E-4001"
            )
        role = await user_repo.get_role_by_code(db, role_code)
        if role is None:
            raise ValidationError(f"Unknown role '{role_code}'", code="RMS-E-4001")
        role_id = role.role_id

    user = await user_repo.update_fields(
        db, user,
        full_name=full_name.strip() if full_name is not None else None,
        email=email,
        designation=(designation.strip() if designation is not None else None),
        role_id=role_id,
        is_active=is_active,
    )
    # role relationship may be stale after a role change — resolve names explicitly
    role_obj = await user_repo.get_role_by_code(db, role_code) if role_code else user.role
    result = await _public_with_photo(user, role_obj.role_code, role_obj.role_name)
    await audit_service.record(
        db, entity_type="USER", entity_id=str(user.user_id), action="UPDATE",
        performed_by=actor_id, before_state=before, after_state=result,
    )
    await db.commit()
    return result


async def set_photo(
    db: AsyncSession, *, user_id: uuid.UUID, actor_id: uuid.UUID,
    data: bytes, content_type: str,
) -> dict:
    """Store a user's profile photo (icon + profile WebP) and mirror it onto any linked
    candidate profile (same email) so the person looks identical everywhere."""
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found", code="RMS-E-4041")

    icon_key, profile_key = await avatar_service.process_and_store(
        owner_type="users", owner_id=user_id, data=data, content_type=content_type,
    )
    await user_repo.set_photo(db, user, icon_key, profile_key)
    linked = await candidate_repo.get_by_email(db, user.email)
    if linked is not None:
        await candidate_repo.set_photo(db, linked, icon_key, profile_key)
    await audit_service.record(
        db, entity_type="USER", entity_id=str(user.user_id), action="PHOTO_UPDATE",
        performed_by=actor_id, after_state={"photo_object_key": profile_key},
    )
    await db.commit()
    return await _public_with_photo(user, user.role.role_code, user.role.role_name)
