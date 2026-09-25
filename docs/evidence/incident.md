# Telemetry and local incident rehearsal

Status: implemented and locally verified; hosted collection and paging are NOT EXECUTED.
Evidence date: 2026-09-25. Windows/Python 3.12.14, real disposable PostgreSQL 17 databases, real local OIDC, synthetic inputs. OpenTelemetry SDK/API/exporter are pinned to 1.44.0.

The API creates a root span and stores payload-free W3C context in the same transaction as a planning revision, explicit job, interpretation, activation, or calendar request. Workers load that context after the commit. Coalesced solves can also link the accepted input revision. Provider proxies record the operation and outcome without arguments or results. The diagnostics table is never consulted for authorization, scheduling, publication ownership, or fencing. `planner.cli prune-traces` removes only context records older than seven days.

The first meaningful handoff tests failed because no durable parent existed; the implementation then passed API → committed interpretation → worker → provider linkage and transaction-rollback tests. Raw results: [red](raw/task-17-handoff-red.txt), [green](raw/task-17-handoff-green.txt). The combined trace, calendar and AI regression bundle passed **45 tests in 22.97 seconds** ([raw](raw/task-17-hooks-green.txt)).

Redaction is an allowlist: operation UUIDs, route templates, method/status, bounded reasons, timing, counts and usage. SQL statements/parameters, exception messages/stack traces, paths/query strings, headers/cookies, prompts, task names and calendar bodies are omitted. Uvicorn access logging remains disabled, including OAuth callback query strings. Metrics reject owner/job IDs as labels. The SDK uses 10% parent-based sampling by default; the bounded in-memory smoke records every span. Load metrics do not depend on trace sampling.

The local collector, Prometheus and Grafana run from digest-pinned images. OTLP/HTTP, database reachability, API histogram and Grafana health were observed; six alert rules passed `promtool check rules` ([collector evidence](raw/task-17-collector-smoke.txt)). Initial smoke caught OpenTelemetry's dimensionless `1` gauge unit producing a `_ratio` suffix; gauges now use no unit for counts, and dashboard/alert names match the actual exporter. API/DB/stage latency buckets use subsecond boundaries.

## Actual incident timeline

`uv run pytest tests/fault/test_dependency_failures.py -q -s` passed **3 tests in 3.78 seconds** ([raw](raw/task-17-incidents.txt)). These are local fault observations, not an availability or production recovery SLA.

| Fault | Observed detection and recovery | Clock qualification |
|---|---|---|
| Disable new connections on one disposable DB | Authenticated request returned redacted 503 / DEPENDENCY_UNAVAILABLE; after restoring the database flag, the next request returned 200. Combined measured interval 0.049 s. Query-string sentinels absent from spans. | Actual wall clock. The app pool was disposed before the outage; no shared database stopped. |
| Synthetic provider throttle | Provider span recorded ProviderError; interpretation persisted FAILED / PROVIDER_THROTTLED. A separate subsequent request with the healthy mock provider persisted READY. | No claim of automatic provider retry or live-provider behavior. |
| Kill an expendable claimed worker process | Durable job remained RUNNING after process death; expired-lease gauge/reason detected the loss, reconciler returned it to QUEUED, a higher fencing token solved it to SUCCEEDED with the original request trace. | Actual process termination; **31 seconds of lease time were advanced by the injected fixed clock**, not slept. Entire kill/recovery phase measured 1.769 s wall time. |

The killed-worker root cause is loss of heartbeats while durable RUNNING state survives the host process. Recovery is lease expiry plus a new fencing token; late results from the former claim cannot activate or publish anything. The regression asserts the actual process died, state transition sequence, increased token and preserved trace ancestry. Process-tree cleanup itself has separate Task6 hardening evidence from its owner.

## Reproduce

1. Start the normal synthetic PostgreSQL/OIDC dependencies and migrate head.
2. `docker compose -f infra/observability/compose.yaml up -d`.
3. `uv run python scripts/deployment/observability_smoke.py`.
4. Run API/workers with `PLANNER_OTLP_ENDPOINT=http://127.0.0.1:24318`; optionally set `PLANNER_TRACE_SAMPLE_RATIO=1` for a bounded synthetic demonstration.
5. Open Grafana at http://127.0.0.1:23000 and the provisioned Adaptive Planner operations dashboard. Prometheus is at http://127.0.0.1:29090.
6. `docker compose -f infra/observability/compose.yaml down` stops the disposable local collectors. Local anonymous Grafana is loopback-only; cloud uses CloudWatch/IAM instead.

Dashboards cover API rate/error/latency, database transactions/pool/reachability, durable queue states/age/leases, solve results, calendar lag/conflicts/write states and interpretation outcomes/usage/spend. Cloud collector configuration is prepared but unexecuted. Alert transport/paging must be connected during an approved hosted rehearsal; local Prometheus evaluates rules but sends no external notification.

See [queue recovery](../runbooks/queue.md), [dependencies](../runbooks/dependencies.md), [calendar](../runbooks/calendar.md), [candidate rejection](../runbooks/candidates.md) and [release recovery](../runbooks/deployment.md). OpenTelemetry's [Python instrumentation documentation](https://opentelemetry.io/docs/languages/python/instrumentation/) explains manual spans and explicit parent contexts.
