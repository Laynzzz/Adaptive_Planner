"""Database connections and schema readiness for the API process."""

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError

from planner.settings import Settings


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )


def migration_config() -> Config:
    root = Path(__file__).resolve().parents[5]
    return Config(str(root / "alembic.ini"))


def database_is_ready(engine: Engine, expected_heads: set[str]) -> bool:
    try:
        with engine.connect() as connection:
            current_heads = set(MigrationContext.configure(connection).get_current_heads())
            return bool(expected_heads) and current_heads == expected_heads
    except SQLAlchemyError:
        # Never return connection strings, credentials, or database errors to clients.
        return False


def migration_heads() -> set[str]:
    return set(ScriptDirectory.from_config(migration_config()).get_heads())
