"""Bind calendar OAuth callbacks and retain synthetic provider state across restarts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009_calendar_oauth_mock'
down_revision = '0008_calendar'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('calendar_connections', sa.Column('oauth_state_hash', sa.String(64)))
    op.add_column('calendar_connections', sa.Column('mock_state', postgresql.JSONB(), nullable=False,
                                                   server_default=sa.text("'{}'::jsonb")))
    op.alter_column('calendar_connections', 'mock_state', server_default=None)


def downgrade():
    op.drop_column('calendar_connections', 'mock_state')
    op.drop_column('calendar_connections', 'oauth_state_hash')
