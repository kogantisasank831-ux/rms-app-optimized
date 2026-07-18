"""initial schema — full DDL (LLD 3.2), extension-free, schema_07

Revision ID: 0001
Revises:
Create Date: 2026-07-09

T-001 transforms applied vs LLD 3.2:
  * no CREATE EXTENSION (denied on shared DB); gen_random_uuid() is built-in on PG16
  * CITEXT email columns -> VARCHAR(255) + UNIQUE INDEX ON (lower(email))
  * all objects created in the connection's search_path (schema_07, set by env.py)
"""
from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# DDL as one readable block. No dollar-quoted bodies here, so splitting on ';'
# at statement boundaries is safe. Executed statement-by-statement for driver
# portability (psycopg extended protocol).
# ---------------------------------------------------------------------------
DDL = """
-- ===== ENUM TYPES =====
CREATE TYPE rrf_status AS ENUM
  ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','ON_HOLD',
   'CANCEL_REQUESTED','CANCELLED','CLOSED');
CREATE TYPE app_stage AS ENUM
  ('APPLIED','SCREENING','SHORTLISTED','INTERVIEW_R1','INTERVIEW_R2',
   'INTERVIEW_MGMT','OFFER','OFFER_ACCEPTED','JOINED');
CREATE TYPE app_status AS ENUM ('ACTIVE','ON_HOLD','REJECTED','WITHDRAWN','HIRED');
CREATE TYPE stage_action AS ENUM ('ADVANCE','REJECT','HOLD','RESUME','WITHDRAW');
CREATE TYPE interview_round AS ENUM ('R1_TECH','R2_TECH','MANAGEMENT');
CREATE TYPE interview_status AS ENUM
  ('SCHEDULED','COMPLETED','CANCELLED','RESCHEDULED','NO_SHOW');
CREATE TYPE interview_mode AS ENUM ('VIDEO','IN_PERSON','TELEPHONIC');
CREATE TYPE recommendation AS ENUM ('SELECT','REJECT','HOLD');
CREATE TYPE offer_status AS ENUM
  ('DRAFT','RELEASED','ACCEPTED','DECLINED','WITHDRAWN','EXPIRED');
CREATE TYPE skill_req_type AS ENUM ('ESSENTIAL','DESIRED');
CREATE TYPE project_type AS ENUM ('T_AND_M','FIXED_FEE');
CREATE TYPE agent_run_status AS ENUM ('SUCCESS','FAILURE','DEGRADED');

-- ===== IDENTITY & REFERENCE =====
CREATE TABLE roles (
  role_id    SMALLSERIAL PRIMARY KEY,
  role_code  VARCHAR(30) NOT NULL UNIQUE,
  role_name  VARCHAR(60) NOT NULL
);

CREATE TABLE users (
  user_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email          VARCHAR(255) NOT NULL,
  password_hash  VARCHAR(120) NOT NULL,
  full_name      VARCHAR(120) NOT NULL,
  role_id        SMALLINT NOT NULL REFERENCES roles(role_id),
  designation    VARCHAR(80),
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));
CREATE INDEX idx_users_role ON users(role_id) WHERE is_active;

CREATE TABLE business_units (
  bu_id           SERIAL PRIMARY KEY,
  bu_name         VARCHAR(100) NOT NULL UNIQUE,
  bu_head_user_id UUID NOT NULL REFERENCES users(user_id)
);

CREATE TABLE skill_master (
  skill_id       SERIAL PRIMARY KEY,
  skill_name     VARCHAR(120) NOT NULL UNIQUE,
  skill_category VARCHAR(80),
  aliases        JSONB NOT NULL DEFAULT '[]',
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  imported_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_skill_aliases_gin ON skill_master USING gin (aliases);

-- ===== RRF AGGREGATE =====
CREATE TABLE rrf (
  rrf_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rrf_code            VARCHAR(20) NOT NULL UNIQUE,
  job_code            VARCHAR(20) UNIQUE,
  position_title      VARCHAR(120) NOT NULL,
  positions_count     SMALLINT NOT NULL CHECK (positions_count > 0),
  assignment_location VARCHAR(80) NOT NULL,
  base_location       VARCHAR(80),
  justification       TEXT NOT NULL,
  project_name        VARCHAR(120) NOT NULL,
  project_type        project_type NOT NULL,
  needed_by_date      DATE NOT NULL,
  salary_range        VARCHAR(60),
  wfh_allowed         BOOLEAN NOT NULL DEFAULT FALSE,
  shift_hours         VARCHAR(40),
  reporting_to        VARCHAR(120),
  scope_of_work       TEXT,
  responsibilities    TEXT,
  education_qualification VARCHAR(200),
  min_experience_years NUMERIC(4,1) NOT NULL DEFAULT 0,
  bu_id               INT NOT NULL REFERENCES business_units(bu_id),
  status              rrf_status NOT NULL DEFAULT 'DRAFT',
  created_by          UUID NOT NULL REFERENCES users(user_id),
  hr_rep_user_id      UUID REFERENCES users(user_id),
  approved_by         UUID REFERENCES users(user_id),
  approved_at         TIMESTAMPTZ,
  held_from_status    rrf_status,
  positions_filled    SMALLINT NOT NULL DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rrf_status ON rrf(status);
CREATE INDEX idx_rrf_created_by ON rrf(created_by);
CREATE INDEX idx_rrf_bu ON rrf(bu_id);

CREATE TABLE rrf_skills (
  rrf_id   UUID NOT NULL REFERENCES rrf(rrf_id) ON DELETE CASCADE,
  skill_id INT  NOT NULL REFERENCES skill_master(skill_id),
  req_type skill_req_type NOT NULL,
  priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  PRIMARY KEY (rrf_id, skill_id)
);

CREATE TABLE rrf_jd_versions (
  jd_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rrf_id     UUID NOT NULL REFERENCES rrf(rrf_id) ON DELETE CASCADE,
  version_no SMALLINT NOT NULL,
  jd_markdown TEXT NOT NULL,
  generated_by_agent BOOLEAN NOT NULL DEFAULT FALSE,
  created_by UUID NOT NULL REFERENCES users(user_id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rrf_id, version_no)
);

CREATE TABLE rrf_status_history (
  history_id  BIGSERIAL PRIMARY KEY,
  rrf_id      UUID NOT NULL REFERENCES rrf(rrf_id) ON DELETE CASCADE,
  from_status rrf_status,
  to_status   rrf_status NOT NULL,
  comment     TEXT NOT NULL CHECK (length(trim(comment)) > 0),
  changed_by  UUID NOT NULL REFERENCES users(user_id),
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rrf_hist ON rrf_status_history(rrf_id, changed_at);

-- ===== CANDIDATE / APPLICATION AGGREGATE =====
CREATE TABLE candidates (
  candidate_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name     VARCHAR(120) NOT NULL,
  email         VARCHAR(255) NOT NULL,
  phone         VARCHAR(20),
  total_experience_years NUMERIC(4,1),
  current_company VARCHAR(120),
  notice_period_days SMALLINT,
  current_ctc   VARCHAR(40),
  expected_ctc  VARCHAR(40),
  source        VARCHAR(60) NOT NULL DEFAULT 'DIRECT',
  cv_object_key VARCHAR(300) NOT NULL,
  cv_file_name  VARCHAR(200) NOT NULL,
  cv_text       TEXT,
  parsed_cv     JSONB,
  created_by    UUID NOT NULL REFERENCES users(user_id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_candidates_email_lower ON candidates (lower(email));

CREATE TABLE applications (
  application_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rrf_id         UUID NOT NULL REFERENCES rrf(rrf_id),
  candidate_id   UUID NOT NULL REFERENCES candidates(candidate_id),
  current_stage  app_stage NOT NULL DEFAULT 'APPLIED',
  status         app_status NOT NULL DEFAULT 'ACTIVE',
  held_from_stage app_stage,
  ai_screen_score NUMERIC(5,2),
  ai_screen_result JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rrf_id, candidate_id)
);
CREATE INDEX idx_app_rrf_stage ON applications(rrf_id, current_stage) WHERE status='ACTIVE';
CREATE INDEX idx_app_status ON applications(status);

CREATE TABLE application_stage_history (
  history_id     BIGSERIAL PRIMARY KEY,
  application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
  from_stage app_stage,
  to_stage   app_stage,
  action     stage_action NOT NULL,
  comment    TEXT NOT NULL CHECK (length(trim(comment)) > 0),
  acted_by   UUID NOT NULL REFERENCES users(user_id),
  acted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_app_hist ON application_stage_history(application_id, acted_at);

-- ===== INTERVIEW AGGREGATE =====
CREATE TABLE interviews (
  interview_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID NOT NULL REFERENCES applications(application_id),
  round          interview_round NOT NULL,
  scheduled_start TIMESTAMPTZ NOT NULL,
  scheduled_end  TIMESTAMPTZ NOT NULL,
  mode           interview_mode NOT NULL DEFAULT 'VIDEO',
  meeting_link   VARCHAR(300),
  location       VARCHAR(200),
  status         interview_status NOT NULL DEFAULT 'SCHEDULED',
  rescheduled_from UUID REFERENCES interviews(interview_id),
  scheduling_agent_run UUID,
  created_by     UUID NOT NULL REFERENCES users(user_id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (scheduled_end > scheduled_start),
  CONSTRAINT uq_interview_app_round_status UNIQUE (application_id, round, status)
    DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX idx_interview_app ON interviews(application_id);
CREATE INDEX idx_interview_time ON interviews(scheduled_start);

CREATE TABLE interview_panelists (
  interview_id UUID NOT NULL REFERENCES interviews(interview_id) ON DELETE CASCADE,
  user_id      UUID NOT NULL REFERENCES users(user_id),
  is_lead      BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (interview_id, user_id)
);
CREATE INDEX idx_panelist_user ON interview_panelists(user_id);

CREATE TABLE interview_feedback (
  feedback_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  interview_id   UUID NOT NULL UNIQUE REFERENCES interviews(interview_id),
  overall_rating NUMERIC(3,1) NOT NULL CHECK (overall_rating BETWEEN 1 AND 5),
  recommendation recommendation NOT NULL,
  strengths      TEXT,
  weaknesses     TEXT,
  raw_notes      TEXT,
  attributes     JSONB NOT NULL DEFAULT '{}',
  ai_summary     JSONB,
  submitted_by   UUID NOT NULL REFERENCES users(user_id),
  submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE interview_skill_ratings (
  feedback_id UUID NOT NULL REFERENCES interview_feedback(feedback_id) ON DELETE CASCADE,
  skill_id    INT  NOT NULL REFERENCES skill_master(skill_id),
  rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  remarks     VARCHAR(300),
  PRIMARY KEY (feedback_id, skill_id)
);

-- ===== OFFER AGGREGATE =====
CREATE TABLE offers (
  offer_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID NOT NULL UNIQUE REFERENCES applications(application_id),
  offer_code     VARCHAR(24) NOT NULL UNIQUE,
  designation    VARCHAR(120) NOT NULL,
  ctc_annual     VARCHAR(60) NOT NULL,
  joining_date   DATE NOT NULL,
  work_location  VARCHAR(120) NOT NULL,
  letter_object_key VARCHAR(300),
  status         offer_status NOT NULL DEFAULT 'DRAFT',
  valid_until    DATE,
  generated_by   UUID NOT NULL REFERENCES users(user_id),
  released_at    TIMESTAMPTZ,
  responded_at   TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE offer_status_history (
  history_id  BIGSERIAL PRIMARY KEY,
  offer_id    UUID NOT NULL REFERENCES offers(offer_id) ON DELETE CASCADE,
  from_status offer_status,
  to_status   offer_status NOT NULL,
  comment     TEXT NOT NULL CHECK (length(trim(comment)) > 0),
  changed_by  UUID NOT NULL REFERENCES users(user_id),
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===== CROSS-CUTTING =====
CREATE TABLE audit_logs (
  audit_id     BIGSERIAL PRIMARY KEY,
  entity_type  VARCHAR(40) NOT NULL,
  entity_id    VARCHAR(64) NOT NULL,
  action       VARCHAR(60) NOT NULL,
  performed_by UUID REFERENCES users(user_id),
  before_state JSONB,
  after_state  JSONB,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id, created_at);

CREATE TABLE ai_agent_runs (
  run_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name    VARCHAR(60) NOT NULL,
  entity_type   VARCHAR(40) NOT NULL,
  entity_id     VARCHAR(64) NOT NULL,
  model         VARCHAR(40) NOT NULL DEFAULT 'claude-opus-4-8',
  input_digest  JSONB,
  output        JSONB,
  prompt_tokens INT,
  completion_tokens INT,
  latency_ms    INT,
  status        agent_run_status NOT NULL,
  error_detail  TEXT,
  triggered_by  UUID REFERENCES users(user_id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_runs_entity ON ai_agent_runs(entity_type, entity_id);
CREATE INDEX idx_agent_runs_name ON ai_agent_runs(agent_name, created_at);

CREATE TABLE notifications (
  notification_id BIGSERIAL PRIMARY KEY,
  user_id      UUID NOT NULL REFERENCES users(user_id),
  title        VARCHAR(160) NOT NULL,
  body         TEXT,
  link_path    VARCHAR(200),
  is_read      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notif_user ON notifications(user_id, is_read);
"""

# Reverse-order drops for a clean downgrade (we do not own the schema, so tables/types only).
_TABLES = [
    "notifications", "ai_agent_runs", "audit_logs", "offer_status_history", "offers",
    "interview_skill_ratings", "interview_feedback", "interview_panelists", "interviews",
    "application_stage_history", "applications", "candidates", "rrf_status_history",
    "rrf_jd_versions", "rrf_skills", "rrf", "skill_master", "business_units", "users", "roles",
]
_TYPES = [
    "agent_run_status", "project_type", "skill_req_type", "offer_status", "recommendation",
    "interview_mode", "interview_status", "interview_round", "stage_action", "app_status",
    "app_stage", "rrf_status",
]


def upgrade() -> None:
    # Drop comment-only lines, then execute each ';'-terminated statement.
    sql = "\n".join(ln for ln in DDL.splitlines() if not ln.strip().startswith("--"))
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            op.execute(stmt)


def downgrade() -> None:
    for t in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    for ty in _TYPES:
        op.execute(f"DROP TYPE IF EXISTS {ty}")
