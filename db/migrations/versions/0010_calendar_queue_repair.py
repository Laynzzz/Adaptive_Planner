"""Forward repair for a development database upgraded during migration8 preparation.

Fresh installations already have these columns from8. Never rewrite an applied
migration to repair a concurrent development upgrade.
"""
from alembic import op

revision = '0010_calendar_queue_repair'
down_revision = '0009_calendar_oauth_mock'
branch_labels = None
depends_on = None


def upgrade():
    for name, sql_type in (
        ('sync_request', 'UUID'), ('publish_request', 'UUID'),
        ('io_lease_token', 'UUID'), ('io_lease_until', 'TIMESTAMPTZ'),
        ('retry_at', 'TIMESTAMPTZ'), ('keep_remote_events', 'BOOLEAN NOT NULL DEFAULT TRUE'),
    ):
        op.execute(f'ALTER TABLE calendar_connections ADD COLUMN IF NOT EXISTS {name} {sql_type}')
    op.execute('ALTER TABLE calendar_connections ALTER COLUMN keep_remote_events DROP DEFAULT')


def downgrade():
    # Columns belong to8. Repairing its transient development drift has no reverse operation.
    pass
