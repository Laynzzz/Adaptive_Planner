"""Durable solve attempts, immutable results and local publication intent."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from planner.db.models import Base, PlanningState


class OwnerDispatchState(Base):
    __tablename__ = "owner_dispatch_state"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    last_dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SnapshotRecord(Base):
    __tablename__ = "immutable_snapshots"
    __table_args__ = (UniqueConstraint("owner_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "what_if_id"],
            ["what_ifs.owner_id", "what_ifs.id"],
            name="fk_job_owned_what_if",
        ),
        ForeignKeyConstraint(
            ["owner_id", "proposal_id"],
            ["proposals.owner_id", "proposals.id"],
            name="fk_job_owned_proposal",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["owner_id", "snapshot_id"], ["immutable_snapshots.owner_id", "immutable_snapshots.id"]
        ),
        Index(
            "uq_running_job_owner",
            "owner_id",
            unique=True,
            postgresql_where=text("state = 'RUNNING'"),
        ),
        Index("ix_jobs_owner_created", "owner_id", "created_at"),
        Index(
            "ix_jobs_ready_owner_created",
            "owner_id",
            "created_at",
            postgresql_where=text("state IN ('QUEUED','RETRY_WAIT')"),
        ),
        Index(
            "ix_jobs_retry_owner_at",
            "owner_id",
            "retry_at",
            postgresql_where=text("state='RETRY_WAIT'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"))
    kind: Mapped[str] = mapped_column(String(20), default="REPLAN", server_default="REPLAN")
    what_if_id: Mapped[UUID | None] = mapped_column()
    planning_revision: Mapped[int] = mapped_column(Integer)
    calendar_revision: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_id: Mapped[UUID | None] = mapped_column()
    state: Mapped[str] = mapped_column(String(20), default="QUEUED")
    fencing_token: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    obsolete: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str | None] = mapped_column(String(100))
    proposal_id: Mapped[UUID | None] = mapped_column()
    result: Mapped[dict | None] = mapped_column(JSONB)


class ProposalRecord(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "snapshot_id"], ["immutable_snapshots.owner_id", "immutable_snapshots.id"]
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    snapshot_id: Mapped[UUID] = mapped_column()
    planning_revision: Mapped[int] = mapped_column(Integer)
    calendar_revision: Mapped[int] = mapped_column(Integer)
    candidate: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20), default="CURRENT")
    publication_state: Mapped[str] = mapped_column(String(30), default="NOT_REQUESTED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProposalBlock(Base):
    __tablename__ = "proposal_blocks"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "proposal_id"], ["proposals.owner_id", "proposals.id"]),
        ForeignKeyConstraint(["owner_id", "task_id"], ["tasks.owner_id", "tasks.id"]),
    )
    owner_id: Mapped[UUID] = mapped_column(primary_key=True)
    proposal_id: Mapped[UUID] = mapped_column(primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column()
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked: Mapped[bool] = mapped_column(Boolean)


class PublicationOperation(Base):
    __tablename__ = "publication_operations"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "proposal_id"], ["proposals.owner_id", "proposals.id"]),
        ForeignKeyConstraint(
            ["owner_id", "proposal_id", "block_id"],
            ["proposal_blocks.owner_id", "proposal_blocks.proposal_id", "proposal_blocks.id"],
            name="fk_publication_owned_block",
        ),
        UniqueConstraint("owner_id", "proposal_id", "block_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    block_id: Mapped[UUID] = mapped_column()
    state: Mapped[str] = mapped_column(String(30), default="PENDING_CONNECTION")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


PlanningState.__table__.append_constraint(
    ForeignKeyConstraint(
        ["owner_id", "active_proposal_id"],
        ["proposals.owner_id", "proposals.id"],
        name="fk_active_proposal_owner",
        use_alter=True,
    )
)
