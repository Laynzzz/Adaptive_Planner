# Task 6 independent review

Date: 2026-09-25. Scope: worker, dispatcher, leases, coalescing, finalization,
activation and their owner-inclusive persistence constraints against plan section
10 and Task 6. Read-only review of implementation; fixes belong to its owner.
Root alone stages and commits shared-worktree files.

## Findings

### P1 — Initializing every dispatch-state row can block unrelated owners

Initial location: `services/planner/src/planner/jobs/dispatcher.py:94`.
Before its SKIP LOCKED selection, the dispatcher bulk-inserted dispatch-state
rows for all pending owners. A concurrent first explicit Generate can have
inserted one such row without committing yet, while that owner's pending row
already exists from an earlier input command. The bulk ON CONFLICT DO NOTHING
waits for that transaction before the dispatcher can consider another owner.

Reproduced against an isolated PostgreSQL database: seed owner A with committed
pending demand but no dispatch-state row; seed/queue eligible owner B; hold A's
planning-state row and insert A's dispatch-state row in an uncommitted transaction;
call `claim_next` in a separate thread. The claim remained blocked beyond 400 ms
despite B being eligible, then completed only after A's transaction released.
This differs from the existing lock-skipping test, which used already initialized
dispatch-state rows and therefore missed the earlier blocking statement.

Smallest fix: lock a candidate PlanningState with SKIP LOCKED before initializing
only that selected owner's dispatch state, or initialize dispatch state during
identity creation. The owner implemented selection of the planning-state row
first, then initialization of only that owner. Full reviewer rerun after the fix:
**30 tests passed in 9.35s**, including the new blocking-initialization regression.
This finding is corrected.

### P2 — An old revision's retry delay blocks fresh input

Location: `services/planner/src/planner/jobs/dispatcher.py:95` during review.
The owner-wide RETRY_WAIT exclusion did not compare the failed job's revision
with the current revision. An ordinary input command updates pending demand but
leaves that old retry record intact, so fresh inputs inherit its delay and attempt
count. This violates the stated two-second eligibility bound even with no solve
in flight.

Reproduced through the real command transaction in an isolated database: fail
three transient attempts at reference time +0, +10, +20 seconds; accept an input
edit at +21 (revision becomes 1); call claim_next at +23. It returns None because
revision 0 is still in RETRY_WAIT. Explicit Generate happens to bypass the delay,
but ordinary edits do not. Smallest fix: treat a retry for a superseded input /
calendar revision as obsolete, making the latest pending revision eligible with
appropriate fresh attempt accounting. The owner scoped retry waiting to current
input/calendar revision and reset attempts when claiming/enqueuing changed inputs.
Reviewer inspected both paths and reran the full target suite: **31 passed in
10.39s**, including the new revision-delay/attempt-reset case. Corrected.

### P1 — Blocking control probes must not extend child execution

Initial location: `services/planner/src/planner/jobs/subprocesses.py:26`.
Cancellation/heartbeat callbacks perform database operations. A wall-deadline
check in the same synchronous loop cannot run while a callback is stalled.
The owner added an independent deadline timer that kills the child even while
the state-check callback is blocked. The regression uses a one-second state
probe, 0.2-second child budget and a child that would write a marker at 0.7 seconds;
the marker is absent and WALL_TIMEOUT is retained. This correction was present
during the reviewer's full 29-test worker/fairness/fault run, which passed.

The distinction matters: the child execution deadline is enforced independently;
the wrapper may return later while a blocked database operation finishes. Do not
claim every end-to-end call or shutdown completes within the child CPU budget.

### P1 — Non-solution statuses were previously flattened during finalization

Cross-boundary finding also recorded in `task-3-7-review.md`: INFEASIBLE/UNKNOWN
empty candidates were validated as schedules, overwriting their diagnostic facts
with missing-work violations and changing their reason to INVALID_CANDIDATE.
Corrected by validating claimed FEASIBLE/OPTIMAL schedules while retaining
non-solution status/report. Reviewer reran all three parameterized cases
(INFEASIBLE, UNKNOWN, MODEL_INVALID): 3 passed in 0.82s.

## Other boundaries inspected

- Claims hold only short transactions, snapshot current inputs while the owner
  planning-state row is locked, and use a global advisory lock for the two-slot
  claim decision. Solver subprocesses receive serialized immutable snapshots,
  never a database session.
- Partial unique running-owner index prevents two active jobs for one owner.
  Claim tokens increment on takeover; heartbeat/finalization require the current
  token and unexpired lease. Current revision and calendar revision gate results.
- Reconciliation restores expired claims and orphan retry demand. Transient
  attempts cap at five with bounded jittered delay; permanent failures do not
  retry. Successful repeated finalization returns the persisted proposal ID.
- Finalization re-reads the persisted immutable snapshot rather than trusting a
  modified worker Claim object. Independent validation gates proposal creation.
- Activation takes the owner lock, checks current input/calendar revision,
  snapshot identity, validity and current time, then atomically writes selection,
  audit and per-block publication intent. New activation supersedes the old active
  proposal; no remote calendar operation is represented as completed.
- Migrations through `b98ef88cd5bf` add owner-inclusive active-proposal, job-result,
  snapshot, task-block and publication-block links, plus immutability guards on
  snapshots/candidate payloads/proposal blocks. Scoped SQL mutation regressions
  exercise these constraints below the API.
- Worker shutdown stops new claims and releases/defers in-flight work; child wall
  timeout may return only a freshly independently validated greedy fallback.

## Fresh verification

Command: `uv run pytest tests/integration/test_jobs.py
tests/integration/test_fairness.py tests/fault/test_job_recovery.py -q`.
Reviewer observed **29 passed in 9.26s**, before the new dispatch-initialization
regression was added. Includes real local PostgreSQL, a real child solver process,
lease/fencing/crash paths, two-slot/ten-owner dispatch rounds, current-time
activation rejection, immutable storage and graceful worker stop. Isolated
synthetic databases were removed by the fixture. No cloud failover or production
throughput claim follows from these checks.

After the dispatch-initialization correction, the full reviewer rerun passed 30
tests in 9.35s. After the fresh-revision retry correction, the same command passed
**31 tests in 10.39s**. Scoped Ruff over jobs, plans, job models and the three test
files also passed. No remaining blocking finding in the reviewed Task 6 scope.
Parent owns complete integrated checks and the coordinated commit.
