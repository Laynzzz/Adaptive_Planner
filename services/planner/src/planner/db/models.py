"""Relational ownership and atomic command storage."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Identity(Base):
    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")


class PlanningState(Base):
    __tablename__ = "user_planning_state"
    __table_args__ = (CheckConstraint("revision >= 0"),)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    active_proposal_id: Mapped[UUID | None] = mapped_column(nullable=True)
    calendar_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginFlow(Base):
    __tablename__ = "login_flows"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(128))
    verifier: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        CheckConstraint("remaining_minutes >= 0"),
        CheckConstraint("priority >= 1 AND priority <= 5"),
        CheckConstraint("state IN ('TODO', 'IN_PROGRESS', 'DONE', 'CANCELLED')"),
        Index("ix_tasks_owner_created_id", "owner_id", "created_at", "id"),
        Index(
            "ix_tasks_active_page",
            "owner_id",
            "created_at",
            "id",
            postgresql_where=text("state IN ('TODO','IN_PROGRESS')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"))
    title: Mapped[str] = mapped_column(String(500))
    remaining_minutes: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    state: Mapped[str] = mapped_column(String(20), default="TODO")
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DependencyEdge(Base):
    __tablename__ = "dependency_edges"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "predecessor_id"], ["tasks.owner_id", "tasks.id"]),
        ForeignKeyConstraint(["owner_id", "successor_id"], ["tasks.owner_id", "tasks.id"]),
        CheckConstraint("predecessor_id <> successor_id"),
    )
    owner_id: Mapped[UUID] = mapped_column(primary_key=True)
    predecessor_id: Mapped[UUID] = mapped_column(primary_key=True)
    successor_id: Mapped[UUID] = mapped_column(primary_key=True)


class Availability(Base):
    __tablename__ = "availability_rules"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    windows: Mapped[list] = mapped_column(JSONB, default=list)


class FixedEvent(Base):
    __tablename__ = "fixed_events"
    __table_args__ = (UniqueConstraint("owner_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSONB)


class CommandReceipt(Base):
    __tablename__ = "command_receipts"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    operation: Mapped[str] = mapped_column(String(300), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSONB)
    status_code: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    operation: Mapped[str] = mapped_column(String(300))
    revision: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PendingReplan(Base):
    """Durable coalesced demand; dispatcher claims/leases are introduced in Task 6."""

    __tablename__ = "pending_replans"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    desired_revision: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    explicit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
