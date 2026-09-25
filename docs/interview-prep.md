# Interview preparation

This is an agent-assisted personal project under implementation. These are study notes, not claims of work experience or user adoption. Personally rehearsed explanations have not yet been recorded.

## Product explanation

Adaptive Planner turns tasks, constraints and available time into reviewed schedules. Its design emphasizes valid plans and understandable changes when work is missed or constraints change.

## Foundation questions

**Why separate readiness from liveness?** Liveness establishes that the process can respond. Readiness additionally checks required database access and schema state. Restarting a healthy process does not repair an unavailable database. Follow-up: what happens when a migration is partially applied? Read `services/planner/src/planner/app.py` and bootstrap integration tests.

**Why lock dependencies?** The same source should resolve to the same package versions on a new machine. Python and npm locks record resolved dependency versions; interpreter and Node versions are recorded separately. Follow-up: do locks guarantee binary reproducibility across operating systems? No; platform wheels and runtime differences still matter.

**Why require real PostgreSQL tests?** SQLite or mocks cannot establish PostgreSQL foreign key, locking, migration or transaction behavior. We isolate test databases so verification cannot overwrite personal data. Follow-up: which tests can stay pure and fast? Time rules, contract validation and algorithms do not require a database.

## Evidence and limits

See [evidence index](evidence-index.md) and [execution status](execution-status.md). No AWS deployment, live calendar integration, AI accuracy or productivity improvement is claimed without its own executed evidence.

## Algorithm and correctness questions

**Why both greedy and CP-SAT?** Greedy gives a fast deterministic baseline; CP-SAT can find feasible placements that greedy ordering misses. Both feed an independent validator. A time-limited solver's UNKNOWN result cannot be described as proof of infeasibility. Follow-up: how did you know the validator was not copying the same bug? Independent tiny enumeration, hand-authored violations and mutation checks. See `solver/validator.py`, `benchmarks/tiny_reference.py`, and the [algorithm report](evidence/task-4-5-solver.md).

**Does a better schedule score mean greater productivity?** No. The score encodes declared preferences with fixed weights. It measures how candidate schedules satisfy that policy, not how people behave. Synthetic tests cannot establish human time savings.

**What is a subtle time bug you encountered?** A previous candidate's slot indices refer to its own UTC-midnight origin. Comparing those indices after the day changes can count unchanged real-world blocks as moved. The correct comparison uses absolute times mapped to the current snapshot. Review caught this boundary beyond the same-day fixtures; the solver evidence records the regression and resolution.

## State and concurrency questions

**How do you prevent stale edits?** Commands carry expected_revision and acquire the owner's planning-state row lock. Input mutation, revision increment, audit, receipt and pending work commit together. A second command using the old revision is rejected. Follow-up: is a version number alone sufficient? No: the read response must pair its data with the corresponding version, and the UI must preserve that pairing.

**Describe the availability bug and correction.** Separate reads could pair old windows with a newer revision; that falsely authorized a subsequent replacement. A controlled second PostgreSQL connection reproduced the lost update. REPEATABLE READ provides a coherent response snapshot, and the UI submits the window snapshot's revision. See [Task 3](evidence/task-3-inputs.md) and [Task 7](evidence/task-7-web.md).

**What if a worker dies or finishes late?** Jobs and leases are stored in PostgreSQL. Recovery retries expired claims with a higher fencing token. Finalization checks token, lease and planning revision before committing a proposal. Follow-up: does this guarantee exactly-once external writes? No; external provider reconciliation is a separate planned mechanism.

**Why PostgreSQL as the queue?** The workload benefits from atomic command-plus-job persistence and needs no separate broker at the current scale. The trade-off is database queue contention, which the plan requires measuring. No throughput claim is made before that study.

## Demonstration to practice later

Sign in as demo A, create a task with a deadline, set an available window, generate and inspect a plan, then activate it. Explain why activation is separate, what happens if another edit occurs, and why Google sync is a distinct future state. Sign in separately as demo B to demonstrate isolation. This is a local synthetic demo, not a production-customer story.

## Adaptation and reviewed input

**Why not subtract elapsed time automatically?** Calendar time is not evidence of completed work. A work log records observed minutes and an explicit remaining estimate separately; corrections append history. A missed block therefore leaves the estimate unchanged until the user updates it. Follow-up: why keep proposal provenance after whole-task completion? Reopening a task must not reuse identities of already completed work. See [Task 8](evidence/task-8-adaptation.md).

**Can an AI interpretation change the calendar?** No. Extraction persists a structured draft. Selected fields and weekday rules pass confirmation, revision, ownership and transactional acceptance before changing inputs. Planning, activation and publication remain separate actions. A source quote establishes provenance but not semantic correctness. Follow-up: what happens on provider timeout? Source text and manual entry remain usable. See [browser evidence](evidence/r2-ui.md) and [evaluation limits](evidence/ai-evaluation.md).

**Why does a good mock score not establish AI quality?** The mock is a fixed local parser, evaluated on authored synthetic families. Its result verifies the scoring pipeline and selected parsing behavior. Live predictions and independent human reference review have their own unexecuted gates. Do not present the 87/90 mock critical-field result as an LLM accuracy claim.

## Calendar failure recovery

**How do retries avoid duplicate remote events?** Stable block-derived IDs, ownership markers and durable operation records let reconciliation find an already committed create after its response was lost. This is recoverable convergence, not a claim of exactly-once networking. Follow-up: what if the user edits the remote event? Conditional ETags reject stale writes, then a fresh read records the actual manual change. See [ADR 0002](adr/0002-calendar-consistency.md).

**Describe an uncovered race and its regression.** A manual move between a remote GET and conditional write was correctly rejected, but the conflict handler initially stored the earlier GET interval. Independent review reproduced the incorrect local reservation. The fix rereads the remote event after the conflict and preserves retryability if that reread fails. Tests also cover 11:07 off-grid moves, which now produce a visible durable failure instead of crashing snapshot capture. See [R2 review](evidence/r2-review.md).

All answers describe agent-assisted implementation and local tests. Personal interview rehearsal, production operation and live Google verification have not been established.
