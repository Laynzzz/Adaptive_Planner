# Failed migration, deployment or workflow smoke

Keep the last known healthy immutable image digest and task-definition ARNs before a release. Migrate with an explicit one-off task and inspect its exit code before updating services. ECS circuit-breaker rollback is configured for startup/health failure; the release script must additionally restore previous task definitions when the application workflow smoke fails.

Never downgrade a database automatically after an application failure. New schema changes must remain compatible with the previous bridge reader, and the compatibility marker must bind its reader list to the exact migrated head. Unknown heads fail readiness. The original unmodified R2 reader used strict head equality; it must first receive the documented readiness bridge before a forward migration can safely use it as a rollback target.

If migration fails, stop rollout, preserve the failed task's redacted error class and inspect the Alembic state. Do not stamp a failed migration as successful. Repair forward after review, or recover into a separate database from a verified backup. Image rollback does not restore deleted data.

Verify both readiness and authenticated synthetic workflow after rollback. The local backup rehearsal creates and restores a separate disposable database, compares logical records, and runs image smoke against the restored database. Live AWS deploy/rollback/restore remain NOT EXECUTED until separately authorized and observed. See the deployment evidence for exact local results and retained-resource inventory.
