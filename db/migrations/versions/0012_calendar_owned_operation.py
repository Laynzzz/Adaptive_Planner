"""Constrain each acknowledged mapping to an operation belonging to its owner."""

from alembic import op

revision = "0012_calendar_owned_operation"
down_revision = "0011_work_log_proposal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_calendar_operation_owner_id", "calendar_write_operations", ["owner_id", "id"]
    )
    op.create_foreign_key(
        "fk_calendar_mapping_owned_operation",
        "block_event_mappings",
        "calendar_write_operations",
        ["owner_id", "operation_id"],
        ["owner_id", "id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_calendar_mapping_owned_operation", "block_event_mappings", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_calendar_operation_owner_id", "calendar_write_operations", type_="unique"
    )
