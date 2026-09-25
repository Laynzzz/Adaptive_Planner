"""Reader compatibility is explicit and bound to the exact live migration head."""

from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def compatible_schema(engine, expected_heads):
    try:
        with engine.connect() as connection:
            actual = set(MigrationContext.configure(connection).get_current_heads())
            if not expected_heads or len(actual) != 1:
                return False
            if actual == expected_heads:
                return True
            if connection.scalar(text("SELECT to_regclass('public.schema_compatibility')")) is None:
                return False
            marker = connection.execute(
                text(
                    "SELECT schema_head, compatible_reader_heads FROM schema_compatibility "
                    "WHERE singleton = true"
                )
            ).one_or_none()
            return bool(
                marker
                and actual == {marker.schema_head}
                and expected_heads.issubset(set(marker.compatible_reader_heads))
            )
    except SQLAlchemyError:
        return False
