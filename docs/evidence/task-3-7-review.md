# Task 3 and Task 7 review

Date: 2026-09-25. Scope: current shared worktree during implementation, against
plan sections 9/15 and Tasks 3/7. This review changed no production or test files.
Implementation owners made the fixes described below. The Task 1 review's known
migration packaging follow-up remains deferred to Task 18 and is not duplicated.

## Findings and dispositions

### P1 — Availability contents and revision could diverge at two boundaries

Frontend location: `apps/web/src/features/Workspace.tsx:140` (corrected line).
The replacement PUT previously combined `availability.data.windows` with
`me.revision`. Independently refreshed queries can have old windows and a newer
identity revision. This allows an old full-list replacement to pass optimistic
concurrency and erase another tab's newly added windows. Reproduction: render
identity revision 4 and availability revision 3; the submitted payload previously
used 4. The owner added a failing component regression and now uses the loaded
availability revision, refreshing availability and identity on 409 while keeping
the entered draft. Re-review: focused frontend tests and typecheck passed.
Evidence: `raw/availability-race-red.txt` and `raw/availability-race-green.txt`.

Backend location: `services/planner/src/planner/api/routes.py:303`.
GET availability originally read windows, identity and planning revision in
separate READ COMMITTED statements. Even the corrected client could receive an
inconsistent pair. An isolated real-PostgreSQL reproduction inserted a concurrent
commit between the window read and the revision read:

```text
racing GET: windows 09:00–10:00, revision 2
actual current: windows 11:00–12:00, revision 2
PUT racing GET payload, expected_revision 2: HTTP 200, revision 3
```

The old hours replaced the committed new hours. Recommended minimal fix: read
contents and revision from one consistent database snapshot. The backend owner
changed the input GET sessions to REPEATABLE READ and added the controlled
interleaving regression. Reviewer rerun:
`uv run pytest tests/integration/test_commands.py::test_availability_payload_and_revision_share_one_database_snapshot -q`
passed (1 test, 0.62s); the stale returned revision now causes 409 and preserves
the newer windows. Both halves of this finding are corrected.

### P2 — Accepted effort values could overflow persistence

Location: `services/planner/src/planner/api/schemas.py:31` and `:53` (corrected).
`remaining_minutes` initially had no upper bound although storage is PostgreSQL
INTEGER. A signed-in POST with `remaining_minutes: 3000000000` reproduced HTTP 500
with no revision change. Smallest fix: reject values outside the persistence
range before writing. The owner added the upper bound to create/patch and a
regression. Reviewer rerun passed; this finding is corrected.

### P2 — Malformed time/cursor values escaped the typed error boundary

Locations: `services/planner/src/planner/api/routes.py:60`, `:139`, `:283`.
Explicit `start: null` in a fixed-event PATCH could raise TypeError; a nonexistent
IANA zone raised ZoneInfoNotFoundError; a base64 cursor with matching owner/filter
but `upper: []` raised IndexError. These are client errors, not server failures.
The owner added input guards/exception mapping and regression cases. Isolated API
checks observed HTTP 422 for the null start and invalid zone, retaining revision
1 after both rejected commands. Focused regression reruns for invalid zone,
malformed cursor, effort overflow and no-store headers passed (4 tests, 1.49s).
Corrected. Prefer explicit shape validation over extending a broad exception
catch as future cursor fields evolve.

### P1 — Failed solve outcomes lose their useful diagnostic report

Locations: `services/planner/src/planner/jobs/handlers.py:52` and
`apps/web/src/features/proposals/PlanPanel.tsx:31` (during initial review).
The worker validates an INFEASIBLE/UNKNOWN non-solution as though it claimed to
be a feasible schedule. Empty blocks then generate WORKLOAD_DEFICIT, replace the
solver's capacity report, and set reason INVALID_CANDIDATE. Separately, the UI
reads only the newest proposal candidate although failed solves create no
proposal; JobView already carries the failed candidate. Thus a normal capacity
failure cannot reach the UI's INFEASIBLE status/structured-conflict rendering.
The existing UNKNOWN component test injected an UNKNOWN proposal that the real
pipeline does not create.

Smallest fix: validate schedule invariants for FEASIBLE/OPTIMAL selection while
preserving non-solution status and facts; display failed `job.candidate` status
and diagnostics without offering activation. Add worker and frontend regressions
for a capacity failure with no proposal. Sent to both implementation owners;
verification pending at report creation.

### P2 — Planning responses initially bypassed generated contract types

Location: `apps/web/src/features/proposals/PlanPanel.tsx:4–38` during review.
The panel hand-declared Proposal/Job shapes, with Job omitting the available
candidate. Generated schema drift checks cannot protect these separate types.
Use generated `components['schemas']['ProposalView']` / `JobView` aliases and the
typed GenerateResponse/ActivationView shapes. The planning endpoints and schema
generation were still being integrated during this review; owner is updating the
aliases. Recheck typecheck and OpenAPI drift after regeneration.

## Checked boundaries and evidence limits

Inspected: OIDC state/nonce/PKCE and standard-library JWT issuer/audience/expiry
validation; opaque server-side sessions, cookie flags/local HTTPS exception,
CSRF/origin checks, logout revocation, private no-store responses; owner-scoped
CRUD and composite dependency foreign keys; owner-state row locking, revision
checks, receipt hash/replay/expiration and same-transaction audit/coalescing;
cursor/filter binding; task draft preservation, explicit activation and stale
proposal guard; generated schema workflow. Current CLI disables raw access
logging and DB engine hides SQL parameters. This is a focused code review and
local verification, not a penetration test or production security certification.

Fresh checks performed:

- `npm run typecheck`: passed.
- `npm run test --workspace apps/web -- --run src/features/Workspace.test.tsx
  src/features/tasks/TaskForm.test.tsx src/features/proposals/PlanPanel.test.tsx`:
  6 tests passed across 3 files.
- A concurrent full Task 3 integration run observed 23 passing tests and the
  newly added effort-overflow regression failing while its implementation was
  being fixed. The focused corrected cases were rerun afterward as recorded
  above; do not present that intermediate full run as green.
- Isolated reviewer databases were created through the project test fixture,
  migrated, authenticated through the real local OIDC provider and dropped by
  that same fixture. Synthetic inputs only; no personal records changed.

The parent agent owns the final complete integration/browser/contract rerun and
evidence reconciliation after remaining fixes land.
