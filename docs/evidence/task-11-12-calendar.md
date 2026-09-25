# Tasks 11–12: Calendar export, mirror and publication recovery

Date: 2026-09-25. Worktree: adaptive-planner-implementation. Local PostgreSQL17,
Python3.12, locked dependencies; each integration/fault test migrates a disposable
database. Provider HTTP tests use httpx.MockTransport; publication faults use a
synthetic fake. No live Google API or OAuth token request was made. Official Google
documentation was read to establish the adapter contract.

Implemented: authorized UTC ICS with stable UIDs, RFC5545 escaping and UTF-8 octet
folding; typed Google adapter; full/incremental staged mirror, pagination and410
rebuild; recurrence expansion requested from provider; transparent/cancelled exclusion;
effective busy union/no-op revision behavior; owner-scoped durable mock; separate
browser-bound OAuth/PKCE and encrypted refresh; durable sync/publication queue;
conditional deterministic-ID publication, ambiguous create/update reconciliation;
manual moves/deletions/marker conflicts; explicit audited resolution and disconnect.

## Verification and red/green evidence

- `task-11-provider-red.txt`: missing implementation; ICS/provider eight tests then passed.
- `task-11-sync-red.txt`: four missing-module failures; `task-11-green.txt`:12 passed.
- `task-12-publication-red.txt`: seven missing-module failures;
  `task-12-publication-green.txt`: seven passed.
- `task-12-commands-red.txt`: missing queue worker; two API tests already passed;
  `task-11-12-calendar-green.txt`: initial23 passed.
- `task-12-etag-red.txt` / `task-12-etag-green.txt`: preserve manual metadata and
  detect edits racing with conditional writes.
- `task-12-revoke-red.txt` / `task-12-revoke-green.txt`: attempt revocation, delete
  failed credentials locally, expose unconfirmed remote revocation.
- Independent review's five findings and reproductions are in `r2-review.md`.
  `task-12-conflict-revision-{red,green}.txt`: publication-discovered commitments
  revision/replan under the owner lock.
- `task-12-auth-fence-red.txt` and `task-12-review-fixes-green.txt`: stale auth failure
  cannot cancel a newer disconnect;22 tests passed in the combined corrective run.
- `task-12-update-ack-red.txt` and the same corrective green run: uncertain successful
  updates reconcile without another write or false manual conflict.
- `task-12-conditional-read-{red,green}.txt`: reread after If-Match failure records
  the actual moved interval;11 publication tests passed.
- `task-12-owned-operation-{red,green}.txt`: direct SQL initially accepted a foreign
  owner's operation link; migration12 rejects it through an owner-inclusive FK.
- `task-12-off-grid-{red,green}.txt`: 11:07–12:07 manual move initially raised
  LOCK_NOT_GRID_ALIGNED;27 publication/time-rule tests passed after repair. A further
  focused check claims and finalizes this input as durable FAILED/MODEL_INVALID.
- Final targeted result: **76 passed in16.53s**, recorded in `raw/task-11-12-final.txt`
  after all calendar changes, including explicit restore and adjacent time/task/CP
  regressions. Ruff passed for all owned production and test files.
  Browser evidence is separately run and maintained by root in `calendar-browser.txt`.

Two local intermediate failures were setup/edit errors, not product passes: a
temporarily incomplete migration chain produced multiple heads during concurrent
editing (and later a13 predecessor-name typo), and a newly appended test briefly
had an indentation error. These were
corrected before the reported green runs. A warm-candidate solver test initially
used empty optional work as its supposedly invalid candidate; it was corrected to
an actually stale snapshot reference rather than weakening validation.

## Migration chronology

Calendar8 introduced the mirror/mappings/operations. Root applied a development
copy while this agent was still adding its queue columns; this was a coordination
failure, not a supported deployment procedure. Applied8 was then frozen. Migration9
adds OAuth binding and durable mock data. Forward-only repair10 adds the six queue
columns with IF NOT EXISTS so both the development database and fresh8 installations
converge. Migration12 adds the mapping-to-operation owner-inclusive FK after domain11.
Do not edit an applied migration. Announce readiness explicitly before shared DB apply.

## Limits and capability gates

Live Google credentials and a dedicated synthetic calendar have not been supplied;
live access defaults disabled. OAuth, recurrence requests, conditional writes and
revocation are verified at fake HTTP boundaries only. A real dedicated-calendar
connect/import/publish/manual-edit/revoke/cleanup journey remains blocked on secure
local credential setup and explicit authorization. No paid resource was created.

The workspace retains the identity of its first dedicated calendar when reconnecting;
switching to a different calendar while retained mappings exist returns an explicit
conflict. Leases cannot stop already in-flight remote requests. Conflicts remain
visible until explicit resolution; no claim of atomic calendar activation is made.
Two calendar plus two AI worker threads are the configured local I/O bound; arbitrary
extra service replicas would need a shared capacity policy. Provider calls use a
ten-second transport timeout, not a hard end-to-end transaction deadline.

## Learning handoff additions for root

- User flow: activate locally, inspect publication separately, export ICS, connect
  the simulator, synchronize, resolve a manual-edit conflict explicitly.
- Architecture: calendar worker handles remote I/O; PostgreSQL stages input generations
  and records output operations; normalizers and independent validators still guard
  the scheduling boundary.
- Technique: a transactional outbox plus deterministic identities turns uncertain
  acknowledgments into read/reconcile work. ETags protect edits but do not make HTTP
  and database commits atomic. Exercise later: inject a timeout after a successful
  update and explain why the second attempt performs no write.
- Interview: Why not advance the cursor per page? Why does a lease fail to fence an
  already-running HTTP call? Why does an off-grid manual move need a visible conflict
  instead of silently rounding task workload? Use the fault regressions as evidence.

Entry files: `calendar/sync.py`, `calendar/publish.py`, `calendar/reconcile.py`,
`calendar/oauth.py`, `calendar/worker.py`; consistency tradeoffs are in ADR0002.
