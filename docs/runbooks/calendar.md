# Reauthorization or divergent calendar

Symptoms: calendar state requires reauthorization, lag grows, or open conflicts / retryable write operations persist. Inspect the calendar panel and aggregate `planner_calendar_lag_seconds`, `planner_calendar_conflicts` and `planner_calendar_operations`; traces record only provider method, outcome and operation ID.

Reauthorize explicitly through the connection UI. An old worker's authentication failure must not overwrite a newer connection generation or disconnect request. Do not edit encrypted tokens or connection generations manually.

For divergence, sync and inspect the typed conflict. A manual move/deletion is a user decision: use the existing conflict resolution UI rather than overwriting the provider event. An uncertain write is reconciled against its deterministic ID and exact owned payload; do not issue duplicate creates or bypass If-Match. Off-grid commitments are reported as a constraint conflict and remain at their exact provider instant.

Verification: open conflicts are resolved by explicit review, current-generation sync succeeds, publication reaches its expected state, and a repeated sync/publication produces no duplicates. The synthetic provider fault suite covers response loss, conditional-write races and manual changes; it does not prove live Google quotas or consent configuration.
