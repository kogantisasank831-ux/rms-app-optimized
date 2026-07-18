# FEATURE LIST — TCG Digital RMS (Team T-07)

End-to-end, AI-powered recruitment system. Every listed endpoint is implemented and wired
(no dummy controls). Base path `/api/v1`; all responses use the envelope
`{success, data, meta?}` / `{success:false, error:{code,message,details}}`.

Legend — Live: ✅ verified against provided PG/MinIO/Claude · ⏳ offline-verified, live run pending.

## 1. Auth & Identity (T-103)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Login (JWT) | `POST /auth/login` | public | HS256, 8h, bcrypt; login success/failure audited | ✅ |
| Current user | `GET /auth/me` | any | | ✅ |
| Health | `GET /health` | public | DB + MinIO ping | ✅ |

## 2. Skills — Skill Master (T-105, INV-09)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Import xlsx | `POST /skills/import` | ADMIN, HR | upsert by name; canonical vocabulary | ✅ |
| Add skill | `POST /skills` | ADMIN, HR | create custom skill from UI (name/category/aliases); 409 on dup; audited | ✅ |
| Edit skill | `PATCH /skills/{id}` | ADMIN, HR | rename/recategorise/alias from UI; audited | ✅ |
| Typeahead | `GET /skills?q=` | any | matches name + aliases; paginated | ✅ |

## 2b. Employees — Directory & panelist pool (INV-05)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| List directory | `GET /users` | ADMIN, HR, HM | active non-candidates; `include_inactive` for admin view; populates panel picker | ✅ |
| Assignable roles | `GET /users/roles` | ADMIN | role options for new-employee form (excl. CANDIDATE) | ✅ |
| Add employee | `POST /users` | ADMIN | creates staff user → selectable as panelist; audited | ✅ |
| Activate/deactivate | `PATCH /users/{id}` | ADMIN | deactivated users drop out of panel pickers; audited | ✅ |

## 3. Files (T-104)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Presigned download | `GET /files/presign` | ADMIN, HR, HM, INTERVIEWER, CANDIDATE | 15-min URL; BU_HEAD excluded (INV-07) | ✅ |

## 4. RRF — Requisitions (T-201, T-202)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Create (DRAFT) | `POST /rrfs` | HM, ADMIN | auto internal `RRF-YYYY-NNNN` **+ public `JOB-YYYY-NNNN`**; skills w/ req_type+priority | ✅ |
| List (scoped) | `GET /rrfs` | HM(own), HR, BU_HEAD(own BU), ADMIN | paginated | ✅ |
| Detail | `GET /rrfs/{id}` | scoped | skills joined | ✅ |
| Edit | `PATCH /rrfs/{id}` | HM(owner, DRAFT/REJECTED), ADMIN | | ✅ |
| Transitions (G1–G5) | `POST /rrfs/{id}/transition` | per guard table | submit/approve/reject/hold/resume/request_cancel/confirm/decline/cancel | ✅ |

## 5. JD — AI Job Descriptions (T-203, AGENT-2)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Generate JD | `POST /rrfs/{id}/jd/generate` | HM, HR, ADMIN | jd_creation agent → new version | ✅ |
| List versions | `GET /rrfs/{id}/jd` | scoped | | ✅ |
| Save manual JD | `POST /rrfs/{id}/jd` | HM, HR, ADMIN | editable before submit | ✅ |

## 6. Candidates (T-204)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Create (CV upload) | `POST /candidates` | HR, ADMIN | multipart; CV→MinIO; text extract (pdf/docx); email dedupe | ✅ |
| List (scoped) | `GET /candidates` | HR, HM(own RRFs), ADMIN | cv_text excluded | ✅ |
| Detail | `GET /candidates/{id}` | scoped | presigned CV URL + extracted text | ✅ |

## 7. Applications — Pipeline (T-205, G6–G14)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Create (link) | `POST /applications` | HR, ADMIN | dedupe (rrf,candidate); G6 auto→SCREENING | ✅ |
| List (scoped) | `GET /applications?rrf_id&stage&status` | HR, HM(own), ADMIN | | ✅ |
| Detail | `GET /applications/{id}` | scoped | incl. AI screen result | ✅ |
| History | `GET /applications/{id}/history` | scoped | stage timeline | ✅ |
| Transitions | `POST /applications/{id}/transition` | HR, HM(own), ADMIN | advance/reject/hold/resume/withdraw/mark_joined | ✅ |
| AI Screen | `POST /applications/{id}/screen` | HR, ADMIN | resume_screening agent (AGENT-1) | ✅ |
| AI Match | `GET /rrfs/{id}/match-candidates` | HR, HM(own), ADMIN | candidate_matching (AGENT-3) | ⏳ |

## 8. Interviews (T-301, T-302, T-303, T-304)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Schedule | `POST /interviews` | HR, ADMIN | panel 1..5 (INV-05), one lead, dedupe per round | ✅ |
| Suggest slots (AI) | `POST /interviews/suggest-slots` | HR, ADMIN | interview_scheduling (AGENT-4) + deterministic re-check | ⏳ |
| My interviews | `GET /interviews/my` | any panelist | | ✅ |
| By application | `GET /interviews?application_id=` | HR, HM(own), ADMIN | | ✅ |
| Cancel/no-show/reschedule | `PATCH /interviews/{id}` | HR, ADMIN | | ✅ |
| Prior feedback | `GET /interviews/{id}/prior-feedback` | panelist(INV-06), HR, ADMIN | rounds < current only | ✅ |
| Submit feedback (G15) | `POST /interviews/{id}/feedback` | lead panelist, HR, ADMIN | INV-04 one per interview → COMPLETED | ✅ |
| Summarize (AI) | `POST /interviews/{id}/feedback/summarize` | lead, HR, ADMIN | feedback_summarization (AGENT-5) | ✅ |
| Interview detail | `GET /interviews/{id}` | HR, HM(own), ADMIN, panelist | candidate + role + round context + cached questions for the detail screen | ✅ |
| Suggested questions (AI) | `POST /interviews/{id}/questions` | HR, HM(own), ADMIN | interview_questions (AGENT-6) from CV + JD + round; cached on interview (`ai_interview_questions`) | ✅ |
| View questions | `GET /interviews/{id}/questions` | HR, HM(own), ADMIN, panelist | cached AGENT-6 output | ✅ |

## 9. Offers (T-306, G16–G17, INV-10)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| List (offer status) | `GET /offers` | HR, HM, ADMIN | offer status per application (Draft/Offer shared/Accepted/Declined) for the Offers console | ✅ |
| Create draft | `POST /offers` | HR, ADMIN | from application in OFFER stage; dedupe | ⏳ |
| Generate letter | `POST /offers/{id}/generate-letter` | HR, ADMIN | fixed template → PDF (WeasyPrint) / HTML fallback → MinIO | ⏳ |
| Detail | `GET /offers/{id}` | HR, HM, ADMIN | | ⏳ |
| Transitions | `POST /offers/{id}/transition` | HR, ADMIN | release/accept/decline/withdraw; drives G11/G13/G12 | ⏳ |

## 10. Dashboard & Observability (T-401, T-402)
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Metrics | `GET /dashboard/metrics` | HR, ADMIN, HM(own), BU_HEAD(own BU) | 60s TTL cache; described metrics; BU_HEAD RRF-only | ⏳ |
| Audit viewer | `GET /audit?entity_type&entity_id` | ADMIN, HR | paginated | ⏳ |
| Agent runs | `GET /agents/runs?agent_name` | ADMIN, HR | AI observability (INV-12) | ⏳ |

## 11. Career Portal & Candidate Self-Service
Public careers site + candidate self-service, integrated into the real ATS pipeline. Candidates
authenticate via the existing JWT (CANDIDATE role in `users`), linked to a `candidates` profile by email.
The **public job id `JOB-YYYY-NNNN`** is the only requisition identifier exposed publicly; the internal
`rrf_code` is never shown to candidates or unauthenticated visitors.
| Feature | Endpoint | Roles | Notes |
|---|---|---|---|
| Public job feed | `GET /careers/jobs` | public | APPROVED RRFs as job cards; exposes `job_code`, skills, location, exp, deadline | ✅ |
| Candidate signup | `POST /careers/signup` | public | multipart (name/email/password/phone + CV); creates CANDIDATE user + candidate profile; returns JWT | ✅ |
| Apply to job | `POST /careers/apply` | CANDIDATE | creates application on that RRF via real pipeline (auto-screen); dedupe | ✅ |
| My portal | `GET /careers/me` | CANDIDATE | applied jobs + stage/status, scheduled interviews (join link), released/accepted offer + letter URL | ✅ |

Frontend: public `/careers` portal (search + filter), candidate `/careers/signup` & `/careers/login`
(share the auth split-screen design), and `/careers/dashboard` (open roles, application tracker,
interviews with MS-Teams join link, offer letter). Staff login and AppShell redirect CANDIDATE →
`/careers/dashboard`.

## AI Agents (5 mandatory + optional)
1. **resume_screening** (AGENT-1) — ✅ live
2. **jd_creation** (AGENT-2) — ✅ live
3. **candidate_matching** (AGENT-3) — ⏳
4. **interview_scheduling** (AGENT-4) — ⏳
5. **feedback_summarization** (AGENT-5) — ✅ live
6. **interview_questions** (AGENT-6, optional) — ✅ live — suggested interviewer questions from CV + JD + round; cached per-interview

All agents route through the shared `call_claude_json` wrapper: model `claude-opus-4-8`,
60s timeout, transient-only retries, JSON-repair pass, schema validation, and **every** call
logged to `ai_agent_runs` (INV-12). Agent failure never blocks the manual path.

## Invariants (LLD §1.5) — implementation map
| INV | Where |
|---|---|
| 01 comment on every transition | guard tables + DB CHECK on history tables |
| 02 history + audit per transition | services write both in one txn |
| 03 hold/resume anywhere | `held_from_*` + guard rows |
| 04 one feedback/interview | UNIQUE `interview_feedback.interview_id` + 409 RMS-E-4223 |
| 05 panel 1..5 | interview_service validation → RMS-E-4224 |
| 06 prior-feedback scope | server-injected rounds < N |
| 07 BU_HEAD limits | role gates exclude BU_HEAD from candidate/app/interview/offer/files/matching |
| 08 HM cancel two-step | REQUEST_CANCEL → CONFIRM_CANCEL |
| 09 skill master canonical | FK to skill_master; xlsx import |
| 10 fixed offer template | Jinja2 fill of fixed template → MinIO |
| 11 pagination | `utils/pagination` on every list |
| 12 agent logging | `agents/client` always writes ai_agent_runs |
