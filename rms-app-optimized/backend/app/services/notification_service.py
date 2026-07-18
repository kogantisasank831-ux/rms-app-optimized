"""notification_service — in-app notifications (LLD: persisted, no email/SMS gateway).

Does not commit; shares the caller's transaction so notifications land atomically with the
state change that triggered them.
"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str | None,
    title: str,
    body: str | None = None,
    link_path: str | None = None,
) -> None:
    if user_id is None:
        return
    await db.execute(
        text(
            "INSERT INTO notifications (user_id, title, body, link_path) "
            "VALUES (:u, :t, :b, :l)"
        ),
        {"u": str(user_id), "t": title, "b": body, "l": link_path},
    )
