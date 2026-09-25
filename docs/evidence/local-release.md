# Local experimental release verification

Date:2026-09-25. This is a working local release, not a statement that every external or human gate in the plan passed. No push, hosted release or paid provider call was performed.

## Source and clean setup

Implementation uses branch `feat/adaptive-planner` in the managed `adaptive-planner-implementation` worktree. The original checkout is preserved. Checkpoints include process containment`127be0a`, measured experiment`d145c03`, reviewed editing/telemetry`c9d87e6`, delivery`3a870ba`, dependency metadata alignment`a69fec3`, command-contention recovery`937ace1`, and rollback/bootstrap corrections`14422a6`.

A new local clone was created with `git -c core.autocrlf=false clone --no-hardlinks --branch feat/adaptive-planner . .runtime/release-checkout`. It installed its own Python3.12 virtual environment using `uv sync --frozen --all-extras` and its own Node dependencies using `npm ci`; npm reported zero audited vulnerabilities. PostgreSQL17.9 and the actual local Keycloak provider were reused as isolated dependencies, with a newly created synthetic database. No data was copied from the application database.

The initial clone installed the patched lock but exposed a declaration/lock checkpoint mismatch; `a69fec3` committed the matching package declarations. The clone fetched that fix and the subsequent contention fix with fast-forward only. `uv lock --check` passed. This distinction is recorded because `uv sync --frozen` alone does not detect stale requirement declarations.

## Executed checks

| Check | Outcome and evidence |
| --- | --- |
| Python integration/unit/property/fault suite | 332 passed in95.35s ([raw output](raw/final-python.txt)); includes real isolated PostgreSQL/OIDC tests |
| Browser component suite in clean clone |30 tests passed,3.13s ([raw](raw/final-web-components.txt)) |
| Complete Chromium journeys in clean clone at937ace1 |9 passed,30.6s ([raw](raw/final-browser.txt)) |
| Frontend contract and build | TypeScript, generated OpenAPI/client drift check and Vite production build passed ([build](raw/final-build.txt)) |
| Python lint | `uv run ruff check services tests db training benchmarks evals` passed |
| Frozen bytes across checkout | Six selection/model/report/measurement/correction-source artifacts matched exact SHA256 ([hashes](raw/final-byte-check.json)); earlier frozen AI source checks also retained |
| ML boundary and correction tests |43 passed after the audited alias correction ([raw](raw/ml-final-tests.txt)); actual model remained denied |
| Delivery recovery regressions |8 focused tests passed after independent review; hosted execution is unexecuted |

The initial full clean-browser attempt passed8/9. The weekly-rule removal encountered an explicit retryable `COMMAND_IN_PROGRESS` while a worker held the owner row. [Original failure](raw/fresh-browser-first.txt) is retained. The client now retries only this precise409 code, at most three attempts with75/150ms delays, using identical content and Idempotency-Key. Revision conflicts and other errors are not silently retried. Three regression tests cover successful retry, unchanged request identity, bounded failure and non-retry of revision conflict. The complete suite then passed against a second newly created database.

The editing journey exercises task PATCH/cancel, fixed-event edit/delete, availability removal, timezone preview/explicit confirmation in both directions, off-grid09:07 input and visible8-minute rounding, and the evidence page. Review also reproduced a stale commitment draft acquiring a newer revision; the editor now preserves its opening snapshot through refetch and conflict retries. See [final input review](final-input-review.md).

Desktop evidence-page and390px mobile screenshots were visually inspected. The mobile journey asserts no horizontal document overflow. The interface's large raw reports are rendered when expanded; they remain bundled and readable without the API. [Evidence screenshot](raw/editing-evidence.png).

## Release limits

- R1 core planning and R2 local adaptive flows work. Live Google, paid AI predictions and independent human reference review remain unexecuted.
- SQL studies report both improvements and regressions. The full scheduler v2 measurement has a disclosed Windows descendant-supervision flaw; production containment is repaired, but only the v3 smoke was rerun. The full repaired common-budget gate remains open.
- The routing experiment was negative. Original and corrected reports remain linked; no model/threshold was reselected on test. The classifier's20 known test labels were all negative, so no positive-class ability is established. Fixed serving remains active.
- The200-task input ceiling is not demonstrated feasible scheduling capacity. Short-budget large-case completions were poor, and UNKNOWN is not proof of infeasibility.
- Local image, scan, schema bridge and separate-database restore do not substitute for hosted CI/AWS rollout/rollback/restore. See [deployment instructions](../deployment.md) and its capability-specific evidence.
- The two recorded walkthroughs are agent-operated synthetic demonstrations. No voluntary human study, author personal rehearsal, production adoption or productivity gain is claimed.

## Retained resources and cleanup

All fresh-checkout test API/Vite processes and their three workers were stopped after verification. Scheduler/load measurement processes and disposable benchmark databases were removed by their owners. No AWS resources or paid live calls exist from this task.

Intentionally retained loopback Docker services: PostgreSQL25432, Keycloak28080, local observability collector24318/28889, Prometheus29090 and Grafana23000. These consume local resources only. The unrelated preexisting `evidencebench-db-1` container on15432 was not modified.

Retained synthetic databases: `planner` (normal development data), `planner_clean_r1_89ddcdf`, `planner_ui_final_20260925`, `planner_clean_final_20260925`, `planner_clean_verified_20260925`, and three `planner_demo_2026092521…` video/rehearsal databases. They were retained to preserve reproducible evidence, not silently deleted. The ignored `.runtime/` stores full measurements, derived splits, clone, logs and two videos; small manifests/reports/models are committed. Videos and333MB raw measurements are unavailable in a fresh clone unless separately copied or regenerated.

Use the README commands to run the normal workspace. Stop processes in their owning terminals; `docker compose stop` stops application dependencies without deleting volumes. `docker compose -p planner-observability -f infra/observability/compose.yaml stop` stops the observability stack. No billable external resource cleanup is pending.
