"""profile photos — icon + profile object keys on users and candidates

Adds two nullable columns to both `users` and `candidates`:
  * photo_icon_key    — MinIO key of the small (96px) WebP avatar shown throughout lists/nav
  * photo_object_key  — MinIO key of the larger (384px) WebP photo shown on the profile page

Both nullable so existing rows (no photo) remain valid; the UI falls back to initials.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_TABLES = ("users", "candidates")


def upgrade() -> None:
    for tbl in _TABLES:
        op.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS photo_icon_key VARCHAR(300)")
        op.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS photo_object_key VARCHAR(300)")


def downgrade() -> None:
    for tbl in _TABLES:
        op.execute(f"ALTER TABLE {tbl} DROP COLUMN IF EXISTS photo_object_key")
        op.execute(f"ALTER TABLE {tbl} DROP COLUMN IF EXISTS photo_icon_key")
