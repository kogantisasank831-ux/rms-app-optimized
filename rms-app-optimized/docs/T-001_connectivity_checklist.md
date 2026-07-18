# T-001 — Connectivity Checklist (Team T-07)

```yaml
task: T-001 (plan.md P0)
date: 2026-07-09
result: GREEN — 10/10 MUST checks passed
run_with: python scripts/check_connectivity.py   # reads rms-app/.env (gitignored)
network: FortiClient VPN connected (all three ports reachable)
```

## Results

| Check | Result | Detail |
|---|---|---|
| VPN/TCP PostgreSQL 5432 | ✅ PASS | 3.215.221.9:5432 open |
| VPN/TCP MinIO 9000 | ✅ PASS | 3.215.221.9:9000 open |
| PG connect + version | ✅ PASS | **PostgreSQL 16.14** (Debian) |
| PG version ≥ 13 | ✅ PASS | server_version_num=160014 |
| `gen_random_uuid()` built-in | ✅ PASS | works without pgcrypto → **drop pgcrypto dependency** |
| schema `schema_07` exists | ✅ PASS | present on shared DB `hack_db_02` |
| DDL write in `schema_07` | ✅ PASS | create/drop table OK (role `team_07` can DDL in its schema) |
| `CREATE EXTENSION citext` | ⚠️ **DENIED** | `permission denied to create extension "citext"` — role lacks CREATE on database |
| MinIO bucket `bucket-07` | ✅ PASS | accessible |
| MinIO put/get/delete | ✅ PASS | object round-trip OK |
| Claude API (`claude-opus-4-8`) | ✅ PASS | 200 OK, key valid |
| GitLab host `tcgrepo.tcgdigital.com` | ✅ PASS | HTTP 200 (login/push done manually in browser/git) |

## Decisions confirmed for T-102 (migration)

1. **CITEXT is unavailable** (permission denied on shared DB). → Use `VARCHAR` for `users.email`,
   `candidates.email`, `skill_master.skill_name` etc. with **`UNIQUE INDEX ON (lower(col))`** for
   case-insensitive uniqueness, and compare with `lower()` in queries. (ADR-004 fallback is now the
   chosen path, not conditional.)
2. **pgcrypto NOT needed** — `gen_random_uuid()` is built-in on PG 16. Remove `CREATE EXTENSION pgcrypto`
   from the migration.
3. **No `CREATE EXTENSION` at all** in the migration (would fail). Migration must be extension-free.
4. **All objects created in `schema_07`** — Alembic `version_table_schema=schema_07`, models use
   `{"schema": settings.PG_SCHEMA}` or engine `search_path=schema_07`. Confirmed `team_07` has DDL rights there.
5. **MinIO**: single bucket `bucket-07` already exists and is writable — backend must NOT call
   `make_bucket` (permission not verified and unnecessary); use key prefixes only.

## Manual follow-ups (cannot be automated here)

- [ ] Create GitLab project **`submission`** under `hackathon/team-07` (team captain: Ankit Chowdhury).
- [ ] Ensure all team members have TCG GitLab accounts (Azure AD sign-in) + Developer role on subgroup.
- [ ] Confirm the organizer **verification script** contract (what it checks) before T-406.

> Secrets live only in `rms-app/.env` (gitignored) and the T_07.xlsx sheet (also gitignored). Neither
> is ever pushed to the `submission` repo.
