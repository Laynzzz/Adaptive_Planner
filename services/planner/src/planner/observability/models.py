"""Transactional diagnostic context; never consulted for business authorization."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from planner.db.models import Base


class TraceLink(Base):
    __tablename__ = "operation_trace_links"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    traceparent: Mapped[str] = mapped_column(String(55))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
