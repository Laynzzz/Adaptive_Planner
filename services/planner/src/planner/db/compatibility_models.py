"""Schema reader marker metadata; updated only by explicit migrations."""

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from planner.db.models import Base


class SchemaCompatibility(Base):
    __tablename__ = "schema_compatibility"
    __table_args__ = (
        CheckConstraint("singleton = true", name="ck_schema_compatibility_singleton"),
    )
    singleton: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    schema_head: Mapped[str] = mapped_column(String(32))
    compatible_reader_heads: Mapped[list] = mapped_column(JSONB)
