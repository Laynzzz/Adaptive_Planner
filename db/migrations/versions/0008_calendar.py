"""Durable calendar mirror and publication recovery."""
from alembic import op

revision = "0008_calendar"
down_revision = "0007_interpretations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE TABLE calendar_connections (\n\towner_id UUID NOT NULL, \n\tprovider VARCHAR(20) NOT NULL, \n\tcalendar_id VARCHAR(500) NOT NULL, \n\tstate VARCHAR(30) NOT NULL, \n\tencrypted_refresh_token VARCHAR(4096), \n\tsync_token VARCHAR(4096), \n\tgeneration INTEGER NOT NULL, \n\twindow_start TIMESTAMP WITH TIME ZONE, \n\twindow_end TIMESTAMP WITH TIME ZONE, \n\tbusy_hash VARCHAR(64) NOT NULL, \n\tlast_sync_at TIMESTAMP WITH TIME ZONE, \n\tlast_error VARCHAR(40), \n\tlease_token UUID, \n\tlease_until TIMESTAMP WITH TIME ZONE, \n\tsync_request UUID, \n\tpublish_request UUID, \n\tio_lease_token UUID, \n\tio_lease_until TIMESTAMP WITH TIME ZONE, \n\tretry_at TIMESTAMP WITH TIME ZONE, \n\tkeep_remote_events BOOLEAN NOT NULL, \n\tPRIMARY KEY (owner_id), \n\tFOREIGN KEY(owner_id) REFERENCES identities (id)\n)')
    op.execute('CREATE TABLE calendar_oauth_flows (\n\tstate_hash VARCHAR(64) NOT NULL, \n\towner_id UUID NOT NULL, \n\tbrowser_session_hash VARCHAR(64) NOT NULL, \n\tverifier VARCHAR(128) NOT NULL, \n\tcalendar_id VARCHAR(500) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (state_hash), \n\tFOREIGN KEY(owner_id) REFERENCES identities (id)\n)')
    op.execute('CREATE TABLE event_mirrors (\n\towner_id UUID NOT NULL, \n\tevent_id VARCHAR(1024) NOT NULL, \n\tpayload JSONB NOT NULL, \n\tPRIMARY KEY (owner_id, event_id), \n\tFOREIGN KEY(owner_id) REFERENCES calendar_connections (owner_id)\n)')
    op.execute('CREATE TABLE calendar_sync_generations (\n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tbase_generation INTEGER NOT NULL, \n\tstate VARCHAR(30) NOT NULL, \n\t"full" BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (owner_id, id), \n\tFOREIGN KEY(owner_id) REFERENCES calendar_connections (owner_id)\n)')
    op.execute('CREATE TABLE calendar_staged_events (\n\towner_id UUID NOT NULL, \n\tgeneration_id UUID NOT NULL, \n\tevent_id VARCHAR(1024) NOT NULL, \n\tpayload JSONB NOT NULL, \n\tPRIMARY KEY (owner_id, generation_id, event_id), \n\tFOREIGN KEY(owner_id, generation_id) REFERENCES calendar_sync_generations (owner_id, id)\n)')
    op.execute('CREATE TABLE block_event_mappings (\n\towner_id UUID NOT NULL, \n\tblock_id UUID NOT NULL, \n\ttask_id UUID NOT NULL, \n\tevent_id VARCHAR(1024) NOT NULL, \n\tetag VARCHAR(1024) NOT NULL, \n\tpublished_payload JSONB, \n\toperation_id UUID, \n\tstate VARCHAR(30) NOT NULL, \n\tcommitment JSONB, \n\tPRIMARY KEY (owner_id, block_id), \n\tFOREIGN KEY(owner_id, task_id) REFERENCES tasks (owner_id, id), \n\tUNIQUE (owner_id, event_id), \n\tFOREIGN KEY(owner_id) REFERENCES calendar_connections (owner_id)\n)')
    op.execute('CREATE TABLE calendar_write_operations (\n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tproposal_id UUID NOT NULL, \n\tblock_id UUID NOT NULL, \n\taction VARCHAR(10) NOT NULL, \n\tstate VARCHAR(30) NOT NULL, \n\tdesired_payload JSONB, \n\tobserved_payload JSONB, \n\tobserved_etag VARCHAR(1024), \n\tattempts INTEGER NOT NULL, \n\treason VARCHAR(40), \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(owner_id, block_id) REFERENCES block_event_mappings (owner_id, block_id), \n\tFOREIGN KEY(owner_id, proposal_id) REFERENCES proposals (owner_id, id), \n\tUNIQUE (owner_id, proposal_id, block_id, action)\n)')
    op.execute('CREATE TABLE calendar_conflicts (\n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tblock_id UUID NOT NULL, \n\treason VARCHAR(40) NOT NULL, \n\tstate VARCHAR(20) NOT NULL, \n\tremote_payload JSONB, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(owner_id, block_id) REFERENCES block_event_mappings (owner_id, block_id)\n)')


def downgrade():
    op.drop_table('calendar_conflicts')
    op.drop_table('calendar_write_operations')
    op.drop_table('block_event_mappings')
    op.drop_table('calendar_staged_events')
    op.drop_table('calendar_sync_generations')
    op.drop_table('event_mirrors')
    op.drop_table('calendar_oauth_flows')
    op.drop_table('calendar_connections')
