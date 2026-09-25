"""Explicit one-off migration, followed by a separate least-privilege application role."""

import os
import sys

from alembic import command
from psycopg import sql

from planner.db.session import create_db_engine, migration_config
from planner.settings import Settings


def grant_application_access(engine, password, *, role_name="planner_app"):
    # Only the release migration task receives elevated database credentials.
    role = sql.Identifier(role_name)
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            exists = cursor.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s", (role_name,)
            ).fetchone()
            verb = "ALTER" if exists else "CREATE"
            cursor.execute(
                sql.SQL(
                    verb
                    + " ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}"
                ).format(role, sql.Literal(password))
            )
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                ).format(role)
            )
            cursor.execute(
                sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role)
            )
            for table in ("alembic_version", "schema_compatibility"):
                cursor.execute(
                    sql.SQL("REVOKE ALL ON {} FROM {}").format(sql.Identifier(table), role)
                )
                cursor.execute(
                    sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(table), role)
                )
        raw.commit()
    finally:
        raw.close()


def main():
    config = migration_config()
    settings = Settings()
    config.attributes["database_url"] = settings.database_url
    try:
        command.upgrade(config, "head")
        password = os.environ.get("PLANNER_APPLICATION_PASSWORD")
        if password:
            engine = create_db_engine(settings)
            try:
                grant_application_access(engine, password)
            finally:
                engine.dispose()
        print("Migration completed; application schema is ready.")
        return 0
    except Exception as error:
        print(
            "Migration failed (" + type(error).__name__ + "); inspect redacted diagnostics.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
