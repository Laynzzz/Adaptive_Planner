"""Declare the readers verified against this additive schema.

Revision ID: 0016_schema_compatibility
Revises: 0015_observability_links
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016_schema_compatibility"
down_revision = "0015_observability_links"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "schema_compatibility",
        sa.Column("singleton", sa.Boolean(), primary_key=True),
        sa.Column("schema_head", sa.String(32), nullable=False),
        sa.Column("compatible_reader_heads", JSONB(), nullable=False),
        sa.CheckConstraint("singleton = true", name="ck_schema_compatibility_singleton"),
    )
    op.bulk_insert(
        table,
        [
            {
                "singleton": True,
                "schema_head": revision,
                "compatible_reader_heads": [
                    "0014_sql_indexes",
                    "0015_observability_links",
                    revision,
                ],
            }
        ],
    )


def downgrade():
    op.drop_table("schema_compatibility")
