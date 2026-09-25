"""Owner-constrained mirror, staged generations, mappings and recoverable writes."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from planner.db.models import Base


class CalendarConnection(Base):
    __tablename__ = "calendar_connections"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    calendar_id: Mapped[str] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(30), default="CONNECTED")
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(4096))
    sync_token: Mapped[str | None] = mapped_column(String(4096))
    generation: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    busy_hash: Mapped[str] = mapped_column(String(64), default="")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(40))
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_request: Mapped[UUID | None] = mapped_column()
    publish_request: Mapped[UUID | None] = mapped_column()
    io_lease_token: Mapped[UUID | None] = mapped_column()
    io_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    keep_remote_events: Mapped[bool] = mapped_column(Boolean, default=True)
    oauth_state_hash: Mapped[str | None] = mapped_column(String(64))
    mock_state: Mapped[dict] = mapped_column(JSONB, default=dict)


class CalendarOAuthFlow(Base):
    __tablename__ = "calendar_oauth_flows"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"))
    browser_session_hash: Mapped[str] = mapped_column(String(64))
    verifier: Mapped[str] = mapped_column(String(128))
    calendar_id: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventMirror(Base):
    __tablename__ = "event_mirrors"
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_connections.owner_id"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(String(1024), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class SyncGeneration(Base):
    __tablename__ = "calendar_sync_generations"
    __table_args__ = (UniqueConstraint("owner_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("calendar_connections.owner_id"))
    base_generation: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(30), default="STAGING")
    full: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StagedEvent(Base):
    __tablename__ = "calendar_staged_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "generation_id"],
            ["calendar_sync_generations.owner_id", "calendar_sync_generations.id"],
        ),
    )
    owner_id: Mapped[UUID] = mapped_column(primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(1024), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class BlockEventMapping(Base):
    __tablename__ = "block_event_mappings"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "task_id"], ["tasks.owner_id", "tasks.id"]),
        ForeignKeyConstraint(
            ["owner_id", "operation_id"],
            ["calendar_write_operations.owner_id", "calendar_write_operations.id"],
            name="fk_calendar_mapping_owned_operation",
            use_alter=True,
        ),
        UniqueConstraint("owner_id", "event_id"),
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_connections.owner_id"), primary_key=True
    )
    block_id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column()
    event_id: Mapped[str] = mapped_column(String(1024))
    etag: Mapped[str] = mapped_column(String(1024), default="")
    published_payload: Mapped[dict | None] = mapped_column(JSONB)
    operation_id: Mapped[UUID | None] = mapped_column()
    state: Mapped[str] = mapped_column(String(30), default="PENDING")
    commitment: Mapped[dict | None] = mapped_column(JSONB)


class CalendarWriteOperation(Base):
    __tablename__ = "calendar_write_operations"
    __table_args__ = (
        UniqueConstraint("owner_id", "id", name="uq_calendar_operation_owner_id"),
        ForeignKeyConstraint(
            ["owner_id", "block_id"],
            ["block_event_mappings.owner_id", "block_event_mappings.block_id"],
        ),
        ForeignKeyConstraint(["owner_id", "proposal_id"], ["proposals.owner_id", "proposals.id"]),
        UniqueConstraint("owner_id", "proposal_id", "block_id", "action"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    block_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(30), default="PENDING")
    desired_payload: Mapped[dict | None] = mapped_column(JSONB)
    observed_payload: Mapped[dict | None] = mapped_column(JSONB)
    observed_etag: Mapped[str | None] = mapped_column(String(1024))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarConflict(Base):
    __tablename__ = "calendar_conflicts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "block_id"],
            ["block_event_mappings.owner_id", "block_event_mappings.block_id"],
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column()
    block_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str] = mapped_column(String(40))
    state: Mapped[str] = mapped_column(String(20), default="OPEN")
    remote_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
