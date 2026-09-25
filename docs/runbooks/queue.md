# Growing queue or stale worker leases

Symptoms: oldest pending age exceeds 30 seconds, expired leases remain nonzero for 45 seconds, or no solve outcomes appear. Open the operations dashboard and inspect `planner_queue_oldest_age_seconds`, `planner_jobs_by_state`, `planner_jobs_expired_leases`, database reachability and CPU/memory. Do not treat an INFEASIBLE candidate as a stuck job.

Safe read-only diagnosis:

```sql
SELECT state, reason_code, count(*) FROM jobs GROUP BY state, reason_code;
SELECT min(enqueued_at), count(*) FROM pending_replans;
```

Use job IDs in access-controlled traces, never metric labels. A worker can fail while its durable lease remains active; do not force states or clear fencing tokens by SQL.

Restore database access first, then restart the affected worker process/service. The normal loop calls `reconcile_expired`; expired claims become retryable work and a new claim receives a larger fencing token. Check that the queue ages decline, no expired lease persists, and a synthetic proposal reaches a terminal state. Activation remains explicit. The local killed-worker rehearsal advances its fixed lease clock by 31 seconds; production must wait for real lease expiry.

Keep two CPU solve slots and separate provider workers. Adding concurrency without measuring DB/provider pressure can worsen this incident. After recovery, inspect only redacted error class/reason codes; never paste task or calendar payloads into incident logs.
