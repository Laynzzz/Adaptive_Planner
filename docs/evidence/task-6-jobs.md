# Task 6 — durable fair replanning and explicit activation

Date: 2026-09-25. Scope: local PostgreSQL/API/worker scheduling increment. Root will record the commit that includes these files; no full release, cloud, live provider, or Task 8 adaptation gate is claimed.

## Behavior implemented

- Planning inputs continue using the Task 3 owner state and single coalesced `pending_replans` row. Explicit Generate returns a stable durable job ID and bypasses debounce. Ordinary edits retain the oldest enqueue time, use 300ms debounce, and become eligible by two seconds from the original enqueue even during a repeated-edit fixture.
- Dispatch chooses the least recently dispatched eligible owner, then pending age and UUID. PostgreSQL `SKIP LOCKED` covers owner dispatch and planning state rows, so one input transaction does not block another owner. A short advisory transaction lock serializes the global two-slot claim decision across dispatchers; solving and network work never hold that lock.
- Each claim captures a frozen normalized snapshot in immutable storage, increments its fencing token, and receives a 30-second lease. Heartbeat checks revision/token and extends the lease; old tokens cannot finalize. Reconciliation recovers expired leases and missing retry demand. Transient retry delays use deterministic job-derived jitter, exponential growth and a 60-second cap; no more than five attempts. Permanent invalid inputs/results are not retried.
- The separate `python -m planner.jobs.worker` process uses two solve slots. Child solving uses the existing CP-SAT/validated-greedy pipeline with a 2,000ms CP budget. A five-second independent child deadline remains enforceable even when a state-check callback is slow. The parent checks cancellation every 100ms between operations, terminates an observed stale child, and validates any wall-timeout greedy fallback before returning it. Shutdown stops claims and releases in-flight work for retry; unexpected worker failures log only the exception class and leave recoverable leases.
- Finalization validates against the persisted snapshot, not a caller-supplied copy. Invalid claimed schedules cannot become proposals. INFEASIBLE, UNKNOWN and MODEL_INVALID retain their distinct status and diagnostic report instead of being converted into missing-work errors. A repeated acknowledgment of an already committed successful attempt returns its original proposal ID.
- Proposals, snapshots, proposal blocks and publication intent use owner-inclusive relational links. Snapshot records and proposal block rows reject update/delete; candidate payload/reference fields reject update while selection/publication metadata remain changeable.
- Activation takes the owner state lock, checks revision, imported-calendar revision, snapshot hash, independent schedule validity and the actual current clock. It atomically chooses the active proposal, writes an audit event and records per-block publication intent. Selecting another proposal supersedes the prior active proposal. No remote calendar write occurs; the state is explicitly `PENDING_CONNECTION`.
- Owner-scoped generation, job polling, proposal listing/detail and activation routes use the real session/CSRF dependencies. Generation/activation receipts preserve seven-day idempotency without artificially increasing the planning-input revision.

Schema changes are sequential migrations `62879c45fc31`, `2d83e6cceaea`, and `b98ef88cd5bf`. Follow-up migrations were used after the local application had already applied earlier versions, preserving a reproducible upgrade path.

## Verification

Environment: Windows, uv-managed Python 3.12.14, local PostgreSQL 17 container, real local Keycloak login for API checks, the repository dependency locks. Fixed-clock job tests use 2026-09-25 09:00 UTC; each DB test uses its own temporary database.

```powershell
.\.tools\bin\uv.exe run pytest tests/integration/test_jobs.py tests/integration/test_fairness.py tests/integration/test_plan_api.py tests/fault/test_job_recovery.py -q
.\.tools\bin\uv.exe run pytest tests/integration/test_fairness.py::test_ten_queued_owners_receive_a_round_with_two_active_slots -q -s
```

Fresh result: **32 passed in 10.77s**. [Raw final run](raw/task-6-green.txt). Scoped Ruff check across Task 6 production files, migrations and tests: **All checks passed**.

Coverage includes expired-lease takeover and old-worker fencing, immutable snapshots across edits, stale-result rejection, time advancing without an edit, forged worker snapshots, invalid candidates, cross-owner API/DB links, immutable stored payloads, repeat finalization, two same-revision selections, transient/permanent retries, orphan retry recovery, real child termination, real child CP result validation, validated timeout fallback, slow-state-check deadline enforcement and worker shutdown through its actual stop-event path.

Concurrent dispatcher test starts five actual threads and admits exactly two running jobs. A separate test holds one user's input transaction open and confirms another user is dispatched within the test's one-second bound.

The ten-owner round fixture repeatedly requeues completed owners, keeps two logical jobs active at a time, and observes each eligible owner once before repetition. [Raw sequence and measured durations](raw/task-6-fairness.txt): owner labels `0,4,6,2,1,8,5,3,9,7`; in-process greedy plus result-transaction durations `16.462,9.907,9.243,9.903,9.517,12.420,8.420,9.028,8.962,9.214` ms. UUID tie-breaking makes exact label order vary across runs. These durations are not subprocess throughput or Internet-scale fairness measurements.

## Test-first failures and corrections

- Missing job modules initially prevented collection; minimal boundaries then produced ten real DB test failures at the unimplemented enqueue boundary. Implementation made these ten checks pass.
- Additional tests exposed absent active-owner FK, mutable stored payloads and absent process cancellation. Four checks failed before the constraints/triggers/process controller were implemented.
- A regression showed two proposals could remain ACTIVE and an old activation could falsely report success; selecting a new proposal now supersedes the old one.
- A forged snapshot could erase work before final validation, and a lost pending row could strand a retry. Two failed checks led to persisted-snapshot validation and retry reconciliation.
- A held input transaction blocked dispatch to another user; the test timed out before planning-state `SKIP LOCKED` was added.
- Three solver-status regressions failed because non-solution results were incorrectly validated as empty feasible schedules. Their statuses and diagnostics are now retained.
- Job-result owner binding and proposal-block immutability were added after direct-SQL regression failure.
- Timeout fallback, independent deadline enforcement and shutdown behavior each had a failing behavior test before implementation. The slow callback regression previously let a child write beyond its budget.
- Ruff's unused-import cleanup initially removed imported pytest fixture registration, causing seven setup errors. Explicit fixture re-exports corrected that harness issue; it was not treated as a product pass.

## Limits and next checks

- Two CPU slots are active. The planned four-slot provider I/O pool is reserved as configuration only; no LLM/calendar I/O job handlers are running in R1.
- Child lifetime is independently bounded; an unavailable database can still delay the parent callback/result transaction. This is not a universal request-latency guarantee. Lease recovery is the safety mechanism if a worker disappears.
- Shutdown was exercised through the same stop-event path that SIGTERM/SIGINT handlers set. POSIX signal delivery itself was not rehearsed on this Windows host.
- Infinite input changes can prevent a current result. The bounded evidence is dispatch eligibility/fairness and safe supersession, not guaranteed completion while inputs never settle.
- Protected in-progress accounting and lock/move/work-log/what-if product flows remain Task 8. Current activation rejects any proposed block already in the past; Task 8 must explicitly handle an ongoing protected interval without allowing ordinary past work.
- Mid-publication crash recovery and remote convergence remain Task 12. Local publication rows prove durable intent, not any external write.
- Prior candidates retain their original slot indices for provenance. The solver owner is correcting next-day disruption accounting to compare their UTC instants against the new snapshot origin; that scorer correction is separate from this Task 6 evidence.

## Learning handoff

The fencing token answers a different question from a lease: a lease says when a worker's authority expires, while the monotonically increasing token prevents an old worker from committing after a replacement has started. The database transaction selects a snapshot and records authority; the CPU work runs outside it. Read `jobs/dispatcher.py`, `jobs/handlers.py`, `jobs/leases.py`, then the stale-result and takeover tests. Local selection and remote publication are deliberately separate observable states.

## Final review correction

An independent solver-agent review exposed a bulk dispatch-state initialization insert waiting on an unrelated uncommitted owner before the SKIP LOCKED query. A new test reproduced the one-second timeout. The dispatcher now locks an eligible planning state first and initializes only that selected owner's dispatch row, then locks the dispatch state. Five focused fairness tests passed; the complete Task 6 suite then passed 31 tests in 9.99s and scoped Ruff remained clean. The independent deadline-watchdog review finding had already been corrected and covered by the slow-callback regression.


A second review regression proved a new planning revision could inherit an older revision's retry backoff and attempt exhaustion. Retry eligibility now matches both current planning and calendar revisions, and changed inputs reset attempt accounting. The failing two-second fresh-input check now passes; final complete suite: 32 passed in 10.77s, scoped Ruff clean.

