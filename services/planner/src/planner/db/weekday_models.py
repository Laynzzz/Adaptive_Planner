"""Owner-scoped recurring preferences and hard weekday restrictions."""

from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from planner.db.models import Base


class WeekdayRule(Base):
    __tablename__ = "weekday_rules"
    __table_args__ = (
        UniqueConstraint("owner_id", "kind", "weekday"),
        CheckConstraint("weekday >= 0 AND weekday <= 6"),
        CheckConstraint("kind IN ('SOFT_AVOID','HARD_UNAVAILABLE','HARD_NO_DEADLINE')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    weekday: Mapped[int] = mapped_column()
