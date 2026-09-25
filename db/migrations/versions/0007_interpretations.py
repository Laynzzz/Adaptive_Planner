"""Durable reviewed interpretations and conservative spend reservations."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_interpretations"
down_revision = "0006_adaptation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extraction_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("planning_revision", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("reference_now", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("proposal", postgresql.JSONB()),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_task_ids", postgresql.JSONB()),
        sa.UniqueConstraint("owner_id", "id"),
        sa.CheckConstraint("state IN ('QUEUED','RUNNING','READY','FAILED','ACCEPTED')"),
    )
    op.create_index("ix_extraction_proposals_owner_id", "extraction_proposals", ["owner_id"])
    op.create_index(
        "ix_extraction_active_owner",
        "extraction_proposals",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('QUEUED','RUNNING')"),
    )
    op.create_table(
        "ai_spend_budgets",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("reserved_microusd", sa.BigInteger(), nullable=False),
        sa.Column("spent_microusd", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "ai_spend_reservations",
        sa.Column("interpretation_id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("amount_microusd", sa.BigInteger(), nullable=False),
        sa.Column("settled_microusd", sa.BigInteger()),
        sa.Column("actual_cost_known", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id", "interpretation_id"],
            ["extraction_proposals.owner_id", "extraction_proposals.id"],
        ),
    )
    op.execute("""CREATE FUNCTION immutable_interpretation_input() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF ROW(OLD.owner_id,OLD.source_text,OLD.reference_now,
             OLD.timezone,OLD.planning_revision,OLD.mode)
         IS DISTINCT FROM
         ROW(NEW.owner_id,NEW.source_text,NEW.reference_now,NEW.timezone,NEW.planning_revision,NEW.mode)
         OR (OLD.state IN ('READY','ACCEPTED') AND OLD.proposal IS DISTINCT FROM NEW.proposal) THEN
        RAISE EXCEPTION 'interpretation source and completed proposals are immutable';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER immutable_interpretation BEFORE UPDATE ON extraction_proposals "
        "FOR EACH ROW EXECUTE FUNCTION immutable_interpretation_input()"
    )


def downgrade():
    op.drop_table("ai_spend_reservations")
    op.drop_table("ai_spend_budgets")
    op.drop_table("extraction_proposals")
    op.execute("DROP FUNCTION immutable_interpretation_input()")
