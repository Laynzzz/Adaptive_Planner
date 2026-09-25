"""Bootstrap contracts: dependency failure must never masquerade as readiness."""

import socket

from fastapi.testclient import TestClient

from planner.app import create_app
from planner.settings import Settings


def test_liveness_does_not_require_database():
    with TestClient(
        create_app(Settings(database_url="postgresql+psycopg://x:x@127.0.0.1:1/x"))
    ) as api:
        response = api.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_fails_when_database_is_unavailable():
    # Reserve a loopback port without listening, ensuring no unrelated server can answer.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        url = f"postgresql+psycopg://x:private-password@127.0.0.1:{port}/x"
        with TestClient(create_app(Settings(database_url=url))) as api:
            response = api.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "private-password" not in response.text


def test_readiness_fails_on_reachable_but_unmigrated_database(database_url):
    with TestClient(create_app(Settings(database_url=database_url))) as api:
        assert api.get("/health/ready").status_code == 503


def test_readiness_succeeds_after_migrations(migrated_database_url):
    with TestClient(create_app(Settings(database_url=migrated_database_url))) as api:
        response = api.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_rejects_database_at_a_different_revision(migrated_database_url):
    from sqlalchemy import create_engine, text

    engine = create_engine(migrated_database_url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'unknown_revision'"))
    engine.dispose()
    with TestClient(create_app(Settings(database_url=migrated_database_url))) as api:
        assert api.get("/health/ready").status_code == 503


def test_readiness_observes_migration_without_restarting_api(database_url):
    from alembic import command

    from planner.db.session import migration_config

    with TestClient(create_app(Settings(database_url=database_url))) as api:
        assert api.get("/health/ready").status_code == 503
        config = migration_config()
        config.attributes["database_url"] = database_url
        command.upgrade(config, "head")
        assert api.get("/health/ready").status_code == 200


def test_cli_readiness_reports_database_failure():
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "planner.cli", "check-ready"],
        env={**os.environ, "PLANNER_DATABASE_URL": "postgresql+psycopg://x:x@127.0.0.1:1/x"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == "not_ready"


def test_cli_readiness_reports_migrated_database(migrated_database_url):
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "planner.cli", "check-ready"],
        env={**os.environ, "PLANNER_DATABASE_URL": migrated_database_url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ready"
