"""Measured active-page and archived-job dispatch indexes."""
import sqlalchemy as sa
from alembic import op

revision = '0014_sql_indexes'
down_revision = '0013_weekday_rules'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_tasks_active_page', 'tasks', ['owner_id', 'created_at', 'id'],
                    postgresql_where=sa.text("state IN ('TODO','IN_PROGRESS')"))
    op.create_index('ix_jobs_ready_owner_created', 'jobs', ['owner_id', 'created_at'],
                    postgresql_where=sa.text("state IN ('QUEUED','RETRY_WAIT')"))
    op.create_index('ix_jobs_retry_owner_at', 'jobs', ['owner_id', 'retry_at'],
                    postgresql_where=sa.text("state='RETRY_WAIT'"))


def downgrade():
    op.drop_index('ix_jobs_retry_owner_at', table_name='jobs')
    op.drop_index('ix_jobs_ready_owner_created', table_name='jobs')
    op.drop_index('ix_tasks_active_page', table_name='tasks')
