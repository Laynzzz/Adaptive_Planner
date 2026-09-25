"""Database connections and schema readiness for the API process."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine

from planner.settings import Settings


def create_db_engine(settings: Settings) -> Engine:
    from planner.observability.database import instrument_engine

    engine = create_engine(
        settings.database_url,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )
    return instrument_engine(engine)


def migration_config() -> Config:
    root = Path(__file__).resolve().parents[5]
    return Config(str(root / "alembic.ini"))


def database_is_ready(engine: Engine, expected_heads: set[str]) -> bool:
    from planner.db.compatibility import compatible_schema

    return compatible_schema(engine, expected_heads)


def migration_heads() -> set[str]:
    return set(ScriptDirectory.from_config(migration_config()).get_heads())
