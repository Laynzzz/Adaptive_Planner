"""Real PostgreSQL fixtures: one randomly named disposable database per test.

PLANNER_TEST_ADMIN_URL may point to a dedicated test server, never personal data.
Only databases this fixture created are dropped; application database is not modified.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database_url() -> Iterator[str]:
    admin_url = make_url(
        os.environ.get(
            "PLANNER_TEST_ADMIN_URL",
            "postgresql+psycopg://planner:local-planner-only@127.0.0.1:25432/postgres",
        )
    )
    database_name = f"planner_test_{uuid4().hex}"
    dsn = admin_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
        try:
            yield admin_url.set(database=database_name).render_as_string(hide_password=False)
        finally:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture
def migrated_database_url(database_url: str) -> str:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    return database_url
