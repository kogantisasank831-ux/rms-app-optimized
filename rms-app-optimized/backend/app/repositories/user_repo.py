"""user_repo — DB access for User (no business rules)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role, User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(func.lower(User.email) == func.lower(email))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    stmt = select(User).where(User.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_role_by_code(db: AsyncSession, role_code: str) -> Role | None:
    stmt = select(Role).where(Role.role_code == role_code)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_roles(db: AsyncSession, exclude: tuple[str, ...] = ()) -> list[Role]:
    stmt = select(Role).order_by(Role.role_id)
    if exclude:
        stmt = stmt.where(Role.role_code.notin_(exclude))
    return list((await db.execute(stmt)).scalars().all())


async def insert(
    db: AsyncSession, *, email: str, password_hash: str, full_name: str,
    role_id: int, designation: str | None,
) -> User:
    user = User(
        email=email, password_hash=password_hash, full_name=full_name,
        role_id=role_id, designation=designation,
    )
    db.add(user)
    await db.flush()  # populate server defaults (user_id, timestamps)
    return user


async def set_active(db: AsyncSession, user: User, is_active: bool) -> User:
    user.is_active = is_active
    await db.flush()
    return user


async def set_photo(db: AsyncSession, user: User, icon_key: str, profile_key: str) -> User:
    user.photo_icon_key = icon_key
    user.photo_object_key = profile_key
    await db.flush()
    return user


async def update_fields(
    db: AsyncSession, user: User, *, full_name: str | None = None,
    email: str | None = None, designation: str | None = None,
    role_id: int | None = None, is_active: bool | None = None,
) -> User:
    """Apply admin-edited fields (only those provided) to a user row."""
    if full_name is not None:
        user.full_name = full_name
    if email is not None:
        user.email = email
    if designation is not None:
        user.designation = designation or None
    if role_id is not None:
        user.role_id = role_id
    if is_active is not None:
        user.is_active = is_active
    await db.flush()
    return user
