"""Disposable PostgreSQL storage fixtures; never benchmark against the application DB."""

import json
import os
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

CLOCK = datetime(2026, 9, 25, 12, tzinfo=UTC)


@contextmanager
def isolated_database():
    admin_url = make_url(
        os.environ.get(
            "PLANNER_TEST_ADMIN_URL",
            "postgresql+psycopg://planner:local-planner-only@127.0.0.1:25432/postgres",
        )
    )
    name = "planner_bench_" + uuid4().hex
    admin_dsn = admin_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        url = admin_url.set(database=name).render_as_string(hide_password=False)
        try:
            config = Config("alembic.ini")
            config.attributes["database_url"] = url
            command.upgrade(config, "head")
            yield create_engine(url, hide_parameters=True, pool_size=6, max_overflow=2), name
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def copy_rows(cursor, table, columns, rows):
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns))
    )
    with cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def seed_storage(
    engine, *, users, active_tasks, archived_tasks, archived_jobs, pending_per_owner=2
):
    owners = [uuid5(NAMESPACE_URL, f"sql-study-v1/owner/{i}") for i in range(users)]

    def task_id(owner, index):
        return uuid5(owner, f"task/{index}")

    with closing(engine.raw_connection()) as connection:
        with connection.cursor() as cursor:
            copy_rows(
                cursor,
                "identities",
                ["id", "issuer", "subject", "name", "timezone"],
                (
                    (owner, "synthetic-storage-fixture", str(owner), "SQL synthetic owner", "UTC")
                    for owner in owners
                ),
            )
            copy_rows(
                cursor,
                "user_planning_state",
                ["owner_id", "revision", "calendar_revision"],
                ((owner, 0, 0) for owner in owners),
            )
            copy_rows(
                cursor,
                "availability_rules",
                ["owner_id", "windows"],
                (
                    (
                        owner,
                        json.dumps(
                            [
                                {
                                    "start": CLOCK.isoformat(),
                                    "end": (CLOCK + timedelta(days=13)).isoformat(),
                                }
                            ]
                        ),
                    )
                    for owner in owners
                ),
            )
            copy_rows(
                cursor,
                "tasks",
                [
                    "id",
                    "owner_id",
                    "title",
                    "remaining_minutes",
                    "priority",
                    "state",
                    "details",
                    "created_at",
                ],
                (
                    (
                        task_id(owner, i),
                        owner,
                        f"Synthetic stored task {i}",
                        30 if i < active_tasks else 0,
                        3,
                        "TODO" if i < active_tasks else "DONE",
                        "{}",
                        CLOCK + timedelta(seconds=i)
                        if i < active_tasks
                        else CLOCK - timedelta(days=30, seconds=i),
                    )
                    for owner in owners
                    for i in range(active_tasks + archived_tasks)
                ),
            )
            copy_rows(
                cursor,
                "dependency_edges",
                ["owner_id", "predecessor_id", "successor_id"],
                (
                    (owner, task_id(owner, i - 1), task_id(owner, i))
                    for owner in owners
                    for i in range(1, active_tasks + archived_tasks)
                    if i != active_tasks
                ),
            )
            job_columns = [
                "id",
                "owner_id",
                "kind",
                "planning_revision",
                "calendar_revision",
                "state",
                "fencing_token",
                "attempts",
                "obsolete",
                "created_at",
                "finished_at",
                "reason_code",
            ]
            copy_rows(
                cursor,
                "jobs",
                job_columns,
                (
                    (
                        uuid5(owners[i % users], f"archived/{i}"),
                        owners[i % users],
                        "REPLAN",
                        0,
                        0,
                        "FAILED",
                        1,
                        1,
                        False,
                        CLOCK - timedelta(days=30, seconds=i),
                        CLOCK - timedelta(days=29, seconds=i),
                        "SYNTHETIC_ARCHIVED_FIXTURE",
                    )
                    for i in range(archived_jobs)
                ),
            )
            copy_rows(
                cursor,
                "jobs",
                job_columns,
                (
                    (
                        uuid5(owner, f"queued/{j}"),
                        owner,
                        "REPLAN",
                        0,
                        0,
                        "QUEUED",
                        0,
                        0,
                        False,
                        CLOCK - timedelta(seconds=users - i),
                        None,
                        None,
                    )
                    for i, owner in enumerate(owners)
                    for j in range(pending_per_owner)
                ),
            )
            copy_rows(
                cursor,
                "pending_replans",
                ["owner_id", "desired_revision", "updated_at", "explicit", "enqueued_at"],
                (
                    (
                        owner,
                        0,
                        CLOCK - timedelta(seconds=users - i),
                        True,
                        CLOCK - timedelta(seconds=users - i),
                    )
                    for i, owner in enumerate(owners)
                ),
            )
            cursor.execute("ANALYZE")
        connection.commit()
    return owners
