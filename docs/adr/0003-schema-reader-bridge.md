# ADR0003: explicit schema reader bridge

The original readiness probe equated the database Alembic head to the image's baked head. That correctly rejects unknown schemas but also makes a previous image unhealthy immediately after a compatible additive migration, preventing useful image rollback.

Decision: retain exact equality as the normal path. For different heads, read a migration-owned marker only if its recorded schema head exactly equals the live Alembic head. Its explicit compatible-reader list must include the image's baked head. A missing marker, unknown head, empty reader set or database failure remains not-ready. Application credentials can read this marker but cannot update it.

Migration16 records readers14/15/16 after local additive-schema and old-image rehearsal. A bridge image based on the actual R2 revision adds the generic checker plus static-frontend packaging; business code is unchanged. The unmodified R2 image's expected readiness failure is recorded, not relabeled as compatibility. Existing deployments must roll out the bridge before treating it as a rollback target.

Consequence: every future migration must deliberately update the marker and prove the previous reader's required operations. Dropping/renaming columns requires an expand/contract sequence and removal of incompatible readers only after their rollback window ends. This is stricter than automatically accepting every newer migration. Image rollback and data restore remain separate procedures.
