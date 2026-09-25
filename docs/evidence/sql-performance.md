# SQL and mixed-load evidence — Tasks 13–14

Local measured evidence dated 2026-09-25. The adopted change batches dependency reads and adds three partial indexes. All data is synthetic and all database studies create and drop their own PostgreSQL databases. The application/demo database is not reset.

## Environment and scope

Windows, Intel Core i7-13700K (16 physical / 24 logical cores), Python 3.12.14, PostgreSQL 17.9 in the pinned local container. The machine was shared with the two-slot frozen scheduler benchmark, application processes, integration tests and development/build work. These are repeatable local observations, not dedicated-host capacity claims. SQL clients used two concurrent dispatcher threads; HTTP used two production solver slots. Docker/PostgreSQL host CPU and RSS were not independently sampled, so client/process measurements do not represent total machine consumption.

The final SQL study uses manifest `benchmarks/manifests/sql.json` (v4), with 100 reads after five warmups, 20 rolled-back write transactions, and real dispatcher claim/snapshot/lease transactions. The source checkout included `0014_sql_indexes` and concurrent development; source release bundles and run manifests preserve the exact code used for scheduler and HTTP studies. SQL v4 raw JSON preserves DB version, workload/manifest hashes, plans, client CPU/RSS and timing distributions.

## Storage fixtures and correct baseline

Large: 100 owners, 200 active plus 800 archived tasks each (100,000 total tasks), dependency chains within each active/archive partition, 100,000 archived jobs and two queued jobs per owner. Small: five owners, 20 active plus 80 archived tasks each, 1,000 archived jobs and two queued jobs per owner. UUIDs and storage times are deterministic. The SQL-only synthetic identities are never used to bypass authentication. HTTP adds two identities obtained through real local Keycloak login.

The baseline uses the previous correct per-task dependency projection and existing owner indexes. It retains owner predicates and ordered keyset pages. Only the three candidate indexes are removed in the disposable database. Reads alternate first/follow-on pages; the small fixture has an empty second page, explicitly included in its median/query counts. The read microbenchmark excludes session, watermark and revision queries; the separate HTTP run includes them.

## Read and write results

| Fixture | Task page p50 ms before → after | Task page p95 ms | Query count p95 | Write transaction p95 ms |
| --- | ---: | ---: | ---: | ---: |
| small | 7.73 → 2.56 | 16.30 → 3.93 | 21 → 2 | 11.23 → 11.91 |
| large | 39.22 → 4.37 | 46.93 → 5.44 | 51 → 2 | 12.10 → 13.35 |

Each write transaction inserts 100 active tasks, 99 edges and 100 queued jobs, then rolls back; timings include foreign-key and index maintenance. The retained indexes therefore have a measured write cost: roughly 6.1% higher p95 on small data and 10.3% higher p95 on large data. The small dispatcher timing sample is only ten claims and is noisy; earlier candidate runs sometimes regressed rather than improved. We retain that limitation rather than asserting all operations improve.

The final three indexes are `ix_tasks_active_page(owner_id, created_at, id) WHERE state IN (TODO, IN_PROGRESS)`, `ix_jobs_ready_owner_created(owner_id, created_at) WHERE state IN (QUEUED, RETRY_WAIT)` and `ix_jobs_retry_owner_at(owner_id, retry_at) WHERE state = RETRY_WAIT`. A candidate successor dependency index, including a covering variant, was evaluated in v1/v2 but the large query continued to choose the existing composite primary key; it was not adopted.

## Explain plans and dispatcher contention

Large fixture, `EXPLAIN (ANALYZE, BUFFERS)`:

| Query | Execution ms before → after | Shared hit blocks | Scan rows plus filtered rows |
| --- | ---: | ---: | ---: |
| active_task_page | 0.144 → 0.022 | 18 → 3 | 850 → 50 |
| dependency_batch | 0.128 → 0.128 | 14 → 14 | 49 → 49 |
| ready_job | 0.569 → 0.027 | 1013 → 2 | 1001 → 1 |
| dispatch_owner | 6.733 → 0.252 | 2187 → 8 | 100301 → 300 |

Rows are summed at scan nodes, not repeatedly across parent plan nodes; complete plan trees are in raw JSON. The unchanged dependency batch plan is intentional: the main improvement is one batch query instead of fifty round trips.

| Fixture | Claims/sec before → after | Claim p95 ms | Advisory statement p95 ms | Oldest measured claim age seconds | First-cycle owners served |
| --- | ---: | ---: | ---: | ---: | ---: |
| small | 26.79 → 31.24 | 119.52 → 73.86 | 25.42 → 25.18 | 5.17 → 5.10 | 5/5 → 5/5 |
| large | 4.74 → 10.36 | 343.61 → 186.92 | 174.82 → 103.65 | 115.22 → 108.98 | 100/100 → 100/100 |

Every owner received exactly two claims, with zero claim exceptions. Small/large performed 30/600 claim attempts, including 20/400 empty polls; claims/sec includes this polling overhead. Fairness state is reset before each phase and claim clocks advance monotonically. The claim study finalizes each claimed job with the explicit measurement-only failure reason; it measures dispatch, snapshot and lease work, not solver throughput. Solver/provider calls never run under those row locks. Advisory SQL duration includes round trip/execution and is an upper bound on lock wait, not a separately instrumented PostgreSQL wait event.

## HTTP mixed load

Both phases completed **600 timed seconds after 30 seconds warmup** at **2 requests/second**, frozen before comparisons from the 30-second 4 requests/second pilot (120 successful requests). Eight in-flight requests maximum; 60% task pages, 20% identity reads, 10% availability reads and 10% explicit Generate commands. Two real OIDC identities alternate expensive commands. Each identity has 200 active tasks plus 800 archived tasks; the 100-owner storage fixture remains present.

| Metric | Correct baseline | Optimized |
| --- | ---: | ---: |
| Timed requests | 1200 | 1200 |
| HTTP 200 / 202 | 1080 / 120 | 1080 / 120 |
| HTTP errors / timeouts / dropped arrivals | 0 / 0 / 0 | 0 / 0 / 0 |
| All HTTP p50 ms | 43.362 | 13.458 |
| All HTTP p95 ms | 54.006 | 18.309 |
| Task GET p95 ms | 56.360 | 18.302 |
| Generate HTTP 202 p95 ms | 20.652 | 20.791 |
| Queue residence p50 / p95 ms | 80.24 / 127.34 | 43.40 / 105.06 |
| Solver-reported p95 ms | 2034.079 | 2090.116 |
| Ready to inspect p50 / p95 ms | 2811.84 / 2970.92 | 2780.34 / 3126.98 |
| Jobs succeeded / failed | 120 / 0 | 120 / 0 |
| Commands served per owner | 60 / 60 | 60 / 60 |
| Oldest pending age observed seconds | 0.042 | 0.040 |
| Backlog endpoint slope jobs/second | 0.000 | 0.000 |

Task-page p95 improved, but total plan readiness p95 **regressed by about 5.3%** (2.97 to 3.13 seconds) on this shared host. No claim that SQL optimization accelerates the solver is supported. Both owners received 60 successful timed Generate outcomes. All recorded candidates were FEASIBLE; there were no terminal worker errors. Native search-limit reasons were not retained separately in this HTTP projection; the scheduler artifact retains native statuses and explicit timeout controls.

The endpoint backlog slope was zero and five-second queue samples are preserved. This supports the measured two-identity, 2-rps mix for ten minutes, not arbitrary sustained throughput or 100 simultaneously solving owners. The 100-owner SQL fixture tests aggregate storage and dispatch contention separately.

SQL client CPU was 33.953 CPU seconds over 73.630 elapsed seconds with peak RSS 102.5 MiB. HTTP client peak RSS was 126.2 MiB. A later process sampler covered 883.5 seconds (158 samples), with peak sampled process-tree RSS 1497.4 MiB and 71.23 observed CPU-seconds between contiguous samples. These are incomplete resource observations: short-lived child CPU, earlier baseline samples, between-sample peaks and PostgreSQL/container resources are unmeasured. The original sampler retained historical process IDs; analysis reconstructs current ancestry per sample to exclude 3246 stale/recycled entries. Aggregate RSS also counts shared pages multiple times.

The HTTP source bundle predates the process-tree supervision repair. All timed jobs finished within 3.76 seconds, but this run cannot establish a hard Windows descendant CPU cap. The separate v2 scheduler experiment reproduced an escaped-grandchild timeout and is explicitly barred from model promotion. Future runs use the repaired job-object/session supervisor; original measurements are not rewritten. Both disposable HTTP databases were dropped after completion, and the local load server/worker exited.

Queue residence is snapshot creation minus durable job creation; ready latency is terminal job timestamp minus job creation. Solver metadata includes internal model construction and validation, so it is not a pure native solve timing. Feature, greedy, model, native solve, validation and subprocess-startup components are separately measured by `benchmarks.child` and reported in the scheduler evidence. HTTP 202 excludes that background work.

## Verification, failures and reproduction

Meaningful pagination/query-count regression first failed because five dependency reads were observed instead of one; the batching change passed owner/filter/cursor tests. The existing real-PostgreSQL concurrent-dispatcher test also verifies five simultaneous claim attempts cannot exceed the global pool of two. Latest scoped generator/metric/pagination/supervision check: eight tests passed; all 16 real-PostgreSQL job tests passed, including concurrent pool contention; metric denominator regression first failed before the summary implementation. Source lint passes. A post-fix baseline replay additionally reproduced five dependency reads versus one expected ([raw regression](raw/task-13-query-baseline-red.txt)); the current implementation passes ([scoped green](raw/task-13-14-scoped-green.txt)). One initial replay patched a differently imported test module and therefore did not apply; its passing output is retained separately as `task-13-query-baseline-unapplied.txt`, not counted as a red test.

Preserved study history: v1 had a fixed-clock/reset fairness harness flaw; v2 corrected it and tried the ultimately rejected dependency index; v3 accidentally reused an index-loop variable as a report key, obscuring workload labels. V4 corrected that reporting variable and reran both fixtures with exactly the retained three indexes. None of those earlier files are relabeled as final evidence. The calendar migration-10 forward repair predates this study and is not a measured SQL regression.

```powershell
uv run pytest tests/integration/test_pagination.py tests/integration/test_jobs.py -q
uv run python -m benchmarks.sql --manifest benchmarks/manifests/sql.json --compare
uv run python -m benchmarks.restore http-load-v1
node tests/load/workload.js --describe
uv run python -m benchmarks.load --manifest benchmarks/manifests/load.json
```

The Node entry point delegates to the same Python driver; the recorded run invoked Python directly. Use a new manifest output filename for additional evidence. HTTP requires the local Keycloak fixture and free loopback port 38001. Both studies require the local PostgreSQL administrative fixture connection; teardown drops only the generated `planner_bench_<uuid>` database.

Raw evidence: [final SQL v4](raw/sql-comparison-v4.json), [candidate SQL v2](raw/sql-comparison-v2.json), [HTTP](raw/http-mixed-load-v1.json), [sampled HTTP process resources](raw/http-load-process-samples.jsonl), [metric red](raw/task-14-analysis-red.txt), [metric/split green](raw/task-14-analysis-green.txt).

Teaching points: batching changes round trips; partial indexes reduce work over archived rows; index maintenance adds write cost; a fast HTTP 202 proves enqueue latency, not plan readiness; queue age and fairness are separate from aggregate throughput. Read `db/queries.py`, `benchmarks/sql.py`, `benchmarks/load.py` and the actual plan trees. These workloads are AI-assisted synthetic engineering experiments, not customer traffic or user-behavior evidence.
