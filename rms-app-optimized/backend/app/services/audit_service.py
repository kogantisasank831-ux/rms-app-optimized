"""audit_service — append-only writes to audit_logs (INV-02).

Does NOT commit; the calling service commits so the audit row shares the transaction
with the state change it records.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    performed_by: uuid.UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        text(
            "INSERT INTO audit_logs "
            "(entity_type, entity_id, action, performed_by, before_state, after_state) "
            "VALUES (:et, :eid, :act, :pb, CAST(:bs AS jsonb), CAST(:as AS jsonb))"
        ),
        {
            "et": entity_type,
            "eid": entity_id,
            "act": action,
            "pb": str(performed_by) if performed_by else None,
            "bs": json.dumps(before_state) if before_state is not None else None,
            "as": json.dumps(after_state) if after_state is not None else None,
        },
    )
