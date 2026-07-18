"""offer letter fields — monthly_gross + candidate_name override

Adds the two fields the fixed offer letter needs beyond the initial schema:
  * monthly_gross   — shown alongside Total Cost to Company on the letter
  * candidate_name  — optional override of the applicant's name printed on the letter
Both nullable so existing DRAFT offers remain valid.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE offers ADD COLUMN IF NOT EXISTS monthly_gross VARCHAR(60)")
    op.execute("ALTER TABLE offers ADD COLUMN IF NOT EXISTS candidate_name VARCHAR(120)")


def downgrade() -> None:
    op.execute("ALTER TABLE offers DROP COLUMN IF EXISTS candidate_name")
    op.execute("ALTER TABLE offers DROP COLUMN IF EXISTS monthly_gross")
