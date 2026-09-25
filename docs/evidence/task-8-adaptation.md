# Task 8 — explicit progress, protected work, comparison, and previews

Date: 2026-09-25. Scope: backend/domain/worker increment. Root owns the matching UI and browser evidence. This report does not claim the complete release or live calendar integration.

## Implemented behavior

- Progress commands require an explicit revised remaining estimate or completion. Observed minutes are never automatically subtracted. Corrections append new owner-scoped work logs; the original rows reject SQL update/delete. Whole-task completion retains the selected proposal as provenance, so a later correction that reopens the task cannot reuse completed block identities. An optional `block_id` records a completed observed block; omit it for a partial-task observation.
- Locks and moves are revisioned protected inputs separate from immutable proposal history. Moves preserve the selected block ID. In-progress work needs an explicit future expected end within three hours; only its future normalized reservation counts toward remaining work. Completion releases protected inputs. Excess reservation relative to a revised estimate returns `LOCK_EXCEEDS_REMAINING` and rolls back the command.
- Missed scheduled time alone does not change the remaining estimate. Replanning excludes elapsed blocks from identity matching. Completed task/block commitments, including calendar-imported commitments, are not reserved again.
- Deterministic UTC-overlap matching preserves stable identities across slot-origin changes. Protected identities are reserved first. Newly added blocks cannot collide with identities reassigned to retained work. Plan diffs expose retained, moved, added, removed blocks and mechanical reason codes; they do not invent explanations.
- What-if creation stores reviewed hypothetical changes without incrementing the real planning revision or changing active state. Durable WHAT_IF jobs share the bounded solve pool and fenced snapshot/result path. They persist their candidate separately, never create normal proposals or publication operations, and show terminal worker failures. Multiple queued previews remain isolated.
- Applying a preview requires its original revision, READY state, and a successfully validated job. The normal transactional input command applies reviewed changes, increments the revision once, audits and enqueues a real replan. Concurrent applications accept one revision winner. Application does not activate a plan or publish a calendar event.
- Current-clock activation permits a still-running protected IN_PROGRESS block whose start has passed, while ordinary newly scheduled past work remains rejected.

## API and persistence

Authenticated session/CSRF dependencies and existing idempotency receipts cover every mutation. History, protected inputs, previews and active selection use coherent REPEATABLE READ views and owner scope.

| Route | Result |
| --- | --- |
| POST `/tasks/{id}/work-logs`, `/work-logs/{id}/corrections` | log fields and new revision |
| GET `/tasks/{id}/work-logs` | `items`, revision; ascending created_at then ID |
| POST `/blocks/{id}/lock`, `/blocks/{id}/move` | ID, locked, optional interval/source, revision |
| GET `/protected-work` | active protected inputs and revision |
| GET `/active-plan` | selected ProposalView or null, independent of history pagination |
| GET `/proposals/{id}/diff` | structured PlanDiff |
| POST `/what-ifs` | preview ID, durable job ID, state |
| GET `/what-ifs/{id}` | IDs, state, base revision, optional candidate/diff |
| POST `/what-ifs/{id}/apply` | ID, APPLIED, new revision |

Migration `0006_adaptation` adds work logs, protected inputs, previews and job-kind linkage. Additive migration `0011_work_log_proposal` follows calendar migration 10 and enforces owner-inclusive whole-task completion provenance. Applied migrations were not rewritten.

## Verification

Actual TDD failures preceded implementation: initial progress/lock/preview routes returned 404; protected matching reassigned a newly locked ID; unmatched new blocks duplicated a reassigned ID; two previews incorrectly produced three queued jobs; failed previews remained QUEUED; ongoing activation returned CURRENT_TIME_CONFLICT; reopening whole-task completion reused its completed ID. Each received a focused passing regression after correction.

Checks use uv Python 3.12.14, disposable PostgreSQL databases migrated from empty, real local Keycloak sessions and fixed injected clocks. No external calendar or model writes are required.

```powershell
.\.tools\bin\uv.exe run pytest tests/integration/test_adaptation.py tests/unit/test_plan_diff.py tests/integration/test_jobs.py tests/integration/test_fairness.py tests/integration/test_plan_api.py tests/fault/test_job_recovery.py -q
```

Final result: **52 passed in 24.41s**, recorded in [raw/task-8-green.txt](raw/task-8-green.txt). Scoped Ruff: **All checks passed** across owned production and test files. Browser evidence is recorded separately by root, including selection/progress/correction/what-if/move flows.

The tests cover concurrent preview CAS, explicit progress, immutable correction history, cross-owner history rejection, lock conflict rollback, immutable prior candidate after movement, protected ID/diff propagation, completed/calendar commitments, missed work, ongoing activation, preview nonpublication, stale/invalid preview rejection and durable worker regressions.

## Owned files for root integration

- `services/planner/src/planner/api/adaptation.py`, modifications to `api/plans.py`
- `domain/work_logs.py`, `domain/protected_work.py`, `domain/what_ifs.py`, `domain/plan_diff.py`, modification to `domain/plans.py`
- `solver/block_matching.py`
- `db/adaptation_models.py`, modification to `db/job_models.py`
- `jobs/coalescing.py`, `jobs/dispatcher.py`, `jobs/handlers.py`
- migrations `0006_adaptation_add_explicit_progress_protected_work_.py`, `0011_work_log_proposal.py`; adaptation metadata import in shared `db/migrations/env.py`
- `tests/integration/test_adaptation.py`, `tests/unit/test_plan_diff.py`
- this report and `docs/evidence/raw/task-8-green.txt`

No files were staged or committed by this subagent for Task 8; root controls integration.
