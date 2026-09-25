"""Persist reviewed weekday preferences separately from immutable snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0013_weekday_rules"
down_revision = "0012_calendar_owned_operation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "weekday_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["identities.id"]),
        sa.UniqueConstraint("owner_id", "kind", "weekday"),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6"),
        sa.CheckConstraint("kind IN ('SOFT_AVOID','HARD_UNAVAILABLE','HARD_NO_DEADLINE')"),
    )
    op.create_index("ix_weekday_rules_owner_id", "weekday_rules", ["owner_id"])


def downgrade():
    op.drop_index("ix_weekday_rules_owner_id", table_name="weekday_rules")
    op.drop_table("weekday_rules")
