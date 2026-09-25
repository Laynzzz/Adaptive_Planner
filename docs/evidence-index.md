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
| Live AI / Google / AWS | No credentials or spending allowance configured | Not executed |
