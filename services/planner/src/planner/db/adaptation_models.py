"""Revisioned protected-work inputs and append-only progress/preview records."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class WorkLog(Base):
    __tablename__ = "work_logs"
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "proposal_id"],
            ["proposals.owner_id", "proposals.id"],
            name="fk_work_log_owned_proposal",
        ),
        ForeignKeyConstraint(["owner_id", "task_id"], ["tasks.owner_id", "tasks.id"]),
        ForeignKeyConstraint(["owner_id", "correction_of"], ["work_logs.owner_id", "work_logs.id"]),
        ForeignKeyConstraint(
            ["owner_id", "proposal_id", "block_id"],
            ["proposal_blocks.owner_id", "proposal_blocks.proposal_id", "proposal_blocks.id"],
        ),
        CheckConstraint("observed_minutes >= 0"),
        CheckConstraint("new_remaining_minutes >= 0"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    task_id: Mapped[UUID] = mapped_column()
    observed_minutes: Mapped[int] = mapped_column(Integer)
    new_remaining_minutes: Mapped[int] = mapped_column(Integer)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    correction_of: Mapped[UUID | None] = mapped_column()
    proposal_id: Mapped[UUID | None] = mapped_column()
    block_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProtectedWork(Base):
    __tablename__ = "protected_work"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "task_id"], ["tasks.owner_id", "tasks.id"]),
        CheckConstraint('"end" > start'),
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column()
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(30))
    locked: Mapped[bool] = mapped_column(Boolean)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WhatIfRecord(Base):
    __tablename__ = "what_ifs"
    __table_args__ = (UniqueConstraint("owner_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    base_revision: Mapped[int] = mapped_column(Integer)
    changes: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20), default="QUEUED")
    candidate: Mapped[dict | None] = mapped_column(JSONB)
    base_candidate: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
