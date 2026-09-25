"""Persist bounded, payload-free trace context across durable jobs.

Revision ID: 0015_observability_links
Revises: 0014_sql_indexes
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_observability_links"
down_revision = "0014_sql_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operation_trace_links",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("traceparent", sa.String(55), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operation_trace_links_owner_id", "operation_trace_links", ["owner_id"])
    op.create_index("ix_operation_trace_links_created_at", "operation_trace_links", ["created_at"])


def downgrade():
    op.drop_table("operation_trace_links")
