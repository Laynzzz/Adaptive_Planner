"""Durable interpretation queue and conservative live-call spend reservations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from planner.db.models import Base


class InterpretationRecord(Base):
    __tablename__ = "extraction_proposals"
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        CheckConstraint("state IN ('QUEUED','RUNNING','READY','FAILED','ACCEPTED')"),
        Index(
            "ix_extraction_active_owner",
            "owner_id",
            unique=True,
            postgresql_where=text("state IN ('QUEUED','RUNNING')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="QUEUED")
    planning_revision: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    reference_now: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(20))
    proposal: Mapped[dict | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fencing_token: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_task_ids: Mapped[list | None] = mapped_column(JSONB)


class AISpendBudget(Base):
    __tablename__ = "ai_spend_budgets"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    reserved_microusd: Mapped[int] = mapped_column(BigInteger, default=0)
    spent_microusd: Mapped[int] = mapped_column(BigInteger, default=0)


class AISpendReservation(Base):
    __tablename__ = "ai_spend_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "interpretation_id"],
            ["extraction_proposals.owner_id", "extraction_proposals.id"],
        ),
    )
    interpretation_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column()
    amount_microusd: Mapped[int] = mapped_column(BigInteger)
    settled_microusd: Mapped[int | None] = mapped_column(BigInteger)
    actual_cost_known: Mapped[bool] = mapped_column(default=False)
