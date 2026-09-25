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
