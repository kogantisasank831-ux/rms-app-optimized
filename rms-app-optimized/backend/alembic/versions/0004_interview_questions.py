"""AI-suggested interview questions cache on interviews

Adds one nullable JSONB column to `interviews`:
  * ai_interview_questions — full validated output of the interview_questions agent
    (round + this candidate's CV + the role's JD). Cached per-interview so HR/HM/panel
    can view later without re-generating; every generation is also logged to ai_agent_runs.

Nullable so existing interviews (no questions generated yet) remain valid.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS ai_interview_questions JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE interviews DROP COLUMN IF EXISTS ai_interview_questions")
