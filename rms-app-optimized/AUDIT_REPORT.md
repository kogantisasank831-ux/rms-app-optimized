# RMS App — Correctness, Pipeline and Performance Audit

Audit date: 2026-07-15

## Outcome

The supplied application was reviewed across React rendering/state, TanStack Query caching,
authentication, routing, the pipeline state machine, interview scheduling/feedback, API
transactions, storage access and deployment packaging.

The corrected source passes the frontend TypeScript check and production build, and all Python
application/test modules compile. The configured external PostgreSQL host refused connections in
this environment, so database-backed integration tests could not be executed here; the affected
pipeline tests were updated and retained for execution against an available test stack.

## Highest-impact defects corrected

### Pipeline / Kanban workflow

1. **Feedback could succeed while the stage move failed.** The feedback modal previously saved
   feedback and performed the transition itself. When the next interview had not been scheduled,
   feedback was committed but the move failed; retrying then produced a duplicate-feedback error.
   Feedback and movement are now coordinated by the board as a resumable workflow.

2. **Scheduling could succeed but still surface a 500.** The server's best-effort auto-transition
   could leave the SQLAlchemy session in a failed transaction before the response query. The
   session is now rolled back safely, and the successful interview remains committed.

3. **The board trusted stale client stage data after scheduling.** Schedule responses now include
   the authoritative application stage. The client reconciles this value, explicitly completes a
   deferred move only when needed, and verifies the current stage after ambiguous failures.

4. **Cards did not move immediately.** A transition previously invalidated/refetched the whole
   board, leaving the card in the old column until network completion. Cached source and target
   columns are now updated atomically, then only affected columns are revalidated in the
   background. A short arrival animation makes the completed move visually clear.

5. **Concurrent moves could write contradictory history.** Application transitions now lock the
   application row (`SELECT ... FOR UPDATE`) before evaluating guards and writing stage history.

6. **A prior round's feedback could authorize a later move.** Leaving an interview stage now
   requires feedback for that exact current round, both in the UI and on the server. The rule also
   applies when moving from an interview stage to Offer.

7. **The wrong interview could receive quick feedback.** The modal no longer falls back to another
   scheduled round; it only submits against the interview matching the card's current stage.

8. **Rejected/hold recommendations could still advance.** Quick advance is now available only for
   a `SELECT` recommendation.

9. **Pending modals could be dismissed mid-request.** Comment, feedback and scheduling dialogs now
   prevent accidental close/cancel while their mutation or continuation is running.

10. **Role-incompatible actions produced avoidable 403 errors.** Scheduling, feedback and
    mark-joined controls are shown only to roles permitted by the API. Invalid Offer/Accepted
    advance actions and candidate creation on closed/on-hold requisitions are also hidden.

11. **Drag/drop had browser and interaction inconsistencies.** Drops are accepted only for legal
    targets, Firefox receives required drag data, buttons/links do not start card drags, and target
    feedback is reset cleanly. Horizontal wheel handling uses a non-passive native listener, while
    preserving vertical scrolling inside columns.

12. **Pagination/filter state could become inconsistent.** Column pages reset when requisition,
    search, status, sort or page size changes, and out-of-range pages clamp after totals change.

### Rendering, cache and lifecycle stability

- Removed forced route remounting that reset page state and re-requested data on navigation.
- Moved login redirection out of render-time state changes.
- Synchronized React auth state with token expiry and cleared query data on user changes, avoiding
  cross-user cache leakage.
- Deduplicated `/auth/me` hydration under React Strict Mode.
- Fixed stale/loading behavior where cached data could leave a workspace indefinitely loading.
- Replaced artificial blocking loader delays with delayed-display loaders that do not hold ready
  content back.
- Added cleanup for object URLs, timers and idle callbacks.
- Disabled retries for auth/validation/not-found failures and retained one retry for transient
  network/server failures.
- Kept prior page data during pagination where appropriate, reducing visual flashing.

### Performance

- Major pages are route-lazy-loaded rather than bundled into the first screen.
- Initial JavaScript decreased from **497,762 bytes to 311,347 bytes** (about **37.5% smaller**,
  before gzip).
- The pipeline is emitted as its own on-demand chunk (about 41.6 KB before gzip).
- Pipeline mutations refresh only affected columns, the table cache and KPI stats instead of all
  nine columns.
- Dashboard data is prefetched during browser idle time for staff users.

### API/security/deployment

- Restricted the generic storage presign endpoint to administrators and `templates/` keys. CV,
  offer and avatar downloads remain behind their entity-level authorization checks.
- Added explicit timezone, chronological and future-time validation for schedule/reschedule API
  windows; the browser converts `datetime-local` values to ISO timestamps with offsets.
- Added `.env` and local-secret exclusions to `.gitignore` and excluded secret/dependency/cache
  content from the deliverable.
- Replaced placeholder Dockerfiles/Compose with buildable backend/frontend images, Nginx SPA/API
  proxying, PostgreSQL, MinIO initialization, migrations, health checks and persistent volumes.

## Expected pipeline acceptance flows

### Shortlisted → Round 1

1. Drag the card to Round 1 and enter a transition comment.
2. The API reports that Round 1 must be scheduled.
3. The scheduling dialog opens with Round 1 locked.
4. After a successful save, the server auto-advances the application and returns its current
   stage; the card moves immediately to Round 1 and the two columns revalidate quietly.

### Round 1 → Round 2

1. Drag the card to Round 2 and enter a transition comment.
2. When Round 1 feedback is missing, the exact Round 1 feedback dialog opens.
3. After feedback is saved, the original move resumes.
4. When Round 2 is not yet scheduled, the Round 2 scheduling dialog opens.
5. After scheduling, the application stage is reconciled from the server and the card moves to
   Round 2 without attempting a duplicate transition.

The same sequence applies to Round 2 → Management and Management → Offer, with exact-current-round
feedback enforced before leaving each interview stage.

## Verification performed

- `npm run typecheck` — passed.
- `npm run build` — passed (188 modules transformed).
- `python3 -m compileall -q backend/app backend/tests` — passed.
- Docker Compose YAML parse — passed.
- Database-backed interview/feedback/file tests were invoked, but collection could not connect to
  the configured PostgreSQL endpoint (`connection refused`). No claim is made that those live
  integration tests passed in this environment.

## Files most relevant to the pipeline corrections

- `frontend/src/pages/pipeline/Kanban.tsx`
- `frontend/src/components/QuickFeedbackModal.tsx`
- `frontend/src/components/ScheduleInterviewModal.tsx`
- `frontend/src/components/CommentModal.tsx`
- `frontend/src/api/endpoints/applications.ts`
- `frontend/src/api/endpoints/interviews.ts`
- `frontend/src/index.css`
- `backend/app/services/pipeline_service.py`
- `backend/app/services/interview_service.py`
- `backend/app/repositories/application_repo.py`
- `backend/tests/test_feedback.py`
- `backend/tests/test_interviews.py`
