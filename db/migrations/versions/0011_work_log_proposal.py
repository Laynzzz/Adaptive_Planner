"""Bind whole-task completion to its owner-scoped selected proposal."""

from alembic import op

revision = "0011_work_log_proposal"
down_revision = "0010_calendar_queue_repair"
branch_labels = None
depends_on = None


def upgrade():
    op.create_foreign_key(
        "fk_work_log_owned_proposal",
        "work_logs",
        "proposals",
        ["owner_id", "proposal_id"],
        ["owner_id", "id"],
    )


def downgrade():
    op.drop_constraint("fk_work_log_owned_proposal", "work_logs", type_="foreignkey")
