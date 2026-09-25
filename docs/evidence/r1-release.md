# R1 local release verification

Date: 2026-09-25. Code checkpoint `89ddcdf`, followed by browser-harness correction
`67594a3`. Windows 11, Python 3.12.14, Node 22.20.0, locked PostgreSQL/Keycloak
Compose services. All accounts and inputs are synthetic. No external paid calls.

- Integrated Python run: **144 passed in 39.74s**. R2 tests under development were
  excluded explicitly. [Raw output](raw/r1-python-final.txt).
- Additional populated prior-schema upgrade check: **1 passed in 0.40s**;
  pre-scheduling tasks, owner and revision survive migrations through
  `b98ef88cd5bf`, and an old reflected task interface can still read/write.
  [Raw output](raw/r1-migration.txt). This is not an old production image test.
- TypeScript, generated OpenAPI drift, 12 component tests and production web
  build passed at the R1 checkpoint. Later R2 tests are reported separately.
- Independent [input/UI review](task-3-7-review.md) and [queue review](task-6-review.md)
  have no unresolved blocking finding at that checkpoint.
- Fixtures are committed; [SHA-256 manifest](raw/r1-fixture-hashes.json).
  [Solver evidence](task-4-5-solver.md) includes 1,000 invariant examples, 100 tiny
  exhaustive comparisons and the bounds/limitations of the size smoke.

## Fresh-source reproduction

Cloned the local repository (without hard links) into ignored
`.runtime/r1-clean-89ddcdf`, installed `uv sync --frozen --all-extras` into its own
venv and `npm ci` into its own node_modules. Created the dedicated database
`planner_clean_r1_89ddcdf`; applied all five R1 migrations. Used the existing
synthetic Keycloak container, not a production identity service. Started a worker
from that clone, and let Playwright start the cloned API and web server.

The first whole-browser run found two harness defects: an ambiguous status
locator, and parallel files writing to the same demo account. The real API
correctly rejected a competing command; the test incorrectly assumed acceptance.
Retained [failed output](raw/r1-clean-browser.txt). Scoped the readiness locator
and serialized the shared-account journeys. Fetched the local correction commit
into the clone; repeated all four journeys: **4 passed in 11.8s**.
[Green output](raw/r1-clean-browser-green.txt).

The executed journeys cover provider sign-in, two-user task isolation, two tasks
plus work hours, generation, visible proposal, explicit activation, unavailable
backend recovery and mobile layout. [Active desktop](raw/r1-clean-active.png)
and [390px mobile](raw/r1-clean-mobile.png) were visually inspected.

The clean-clone worker and test-started API/web processes were stopped. The
synthetic database and ignored clone are intentionally retained for reproduction;
the main Compose services remain available for R2. No billable resources exist.

## Scope and remaining limits

R1 local gate passed. The 200-task input envelope is guarded, but single-run size
smoke is not a throughput or p95 guarantee. UI currently uses the identity's UTC
timezone. Inputs and conflicts remain visible; no automatic remote publication
is claimed. Live AI quality, live Google synchronization, hosted CI and AWS
deploy/rollback/restore remain unexecuted. R2–R4 gates remain open.
