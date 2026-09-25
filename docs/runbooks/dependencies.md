# Database interruption or provider failure

Symptoms: API server errors, database reachable gauge zero, or interpretation/provider error spans. Compare API 5xx request counts with database latency/pool usage and provider-call stage outcomes. HTTP responses contain a correlation ID that can locate an access-controlled trace.

For a database outage, inspect RDS/container health and security-group/connectivity changes. Keep the API liveness probe independent; readiness must fail. Restore connectivity or the previous approved secret configuration, then verify readiness, an authenticated read, and one synthetic idempotent command. Do not log the connection URL or secret. The local fault test only disables connections on its randomly named disposable database and restores that setting in `finally`.

For throttling, verify live-call enablement, approved allowance and provider rate limits. Preserve the failed interpretation for review; a new request after the provider recovers may succeed. Do not increase spending limits or repeatedly resubmit automatically. Manual task entry remains available. Distinguish throttling, invalid model output, disabled live access and expired worker lease using the persisted reason code.

Verification: API errors return to baseline, DB gauge is one, a newly submitted synthetic interpretation reaches READY, and its output alone has not changed tasks. See `tests/fault/test_dependency_failures.py` for the bounded regression.
