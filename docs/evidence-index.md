# Evidence index

R1 local gate verified. Record local, mocked and live results separately.

| Capability | Evidence | State |
| --- | --- | --- |
| Bootstrap backend | [Task 1 backend](evidence/task-1-backend.md) | Local PostgreSQL checks executed; real OIDC fixtures verified in Task 3 |
| Bootstrap frontend | [Task 1 web](evidence/task-1-web.md) | 3 component tests, build, 2 real browser tests passed |
| Domain rules | [Task 2](evidence/task-2-domain.md) | 31 local tests passed |
| Scheduling algorithms | [Tasks 4–5](evidence/task-4-5-solver.md) | Unit/property/tiny oracle and bounded size smoke executed |
| Authentication/inputs | [Task 3](evidence/task-3-inputs.md) | Ownership, revision races, idempotency and coherent reads verified |
| Durable queue | [Task 6](evidence/task-6-jobs.md), [independent review](evidence/task-6-review.md) | Local lease/fencing/fairness/crash checks passed |
| R1 release | [Release verification](evidence/r1-release.md) | 144 Python tests + prior-schema check; 12 component tests; 4 fresh-source browser journeys |
| Adaptive planning | [Task 8](evidence/task-8-adaptation.md), [R2 interface](evidence/r2-ui.md) | Local work-log, lock, what-if and browser checks executed |
| Reviewed extraction | [AI evaluation](evidence/ai-evaluation.md), [R2 interface](evidence/r2-ui.md) | Frozen mock evaluation and reviewed task/rule acceptance; human/live gates unexecuted |
| Calendar recovery | [Tasks 11–12](evidence/task-11-12-calendar.md), [independent review](evidence/r2-review.md) | Local durable simulator and failure tests; live Google unexecuted |
| Live AI / Google / AWS | No credentials or spending allowance configured | Not executed |
| Reviewed input editing | [Final input review](evidence/final-input-review.md), [local release](evidence/local-release.md) | Revision-captured drafts, timezone confirmation and original-time display verified |
| SQL and real HTTP load | [SQL report](evidence/sql-performance.md) | Both600-second phases; read gains and write/readiness regressions retained |
| Scheduler measurement | [Baseline report](evidence/scheduler-benchmarks.md) |1,000 groups/7,000 runs; full v2 supervision limitation; repaired v3 smoke only |
| ML routing | [Negative experiment](evidence/ml-experiment.md), [corrected summary](evidence/raw/ml-test-summary.json) | Frozen selection; audited alias correction; six failed gates, no promotion |
| Process containment | [Windows/Linux failures and repair](evidence/process-tree-recovery.md) | Actual descendant tests; cannot retroactively repair old measurements |
| Telemetry and incidents | [Incident report](evidence/incident.md) | Local collector/dashboard and injected faults; no production SLO claim |
| Delivery and restore | [Deployment instructions](deployment.md) | Local image/scan/compatibility/restore; AWS and hosted workflow execution remain open |
| Product and technical recordings | [Usability scope](evidence/usability.md), [technical recording](technical-walkthrough.md) | Agent-operated synthetic videos; human sessions unexecuted |
| Integrated local release | [Clean-checkout report](evidence/local-release.md) | Browser/component/backend counts and retained-resource inventory |
