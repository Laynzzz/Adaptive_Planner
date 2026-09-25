"""A populated prior input schema survives additive scheduling migrations."""

from uuid import uuid4

from alembic import command
from sqlalchemy import MetaData, Table, create_engine, select

from planner.db.session import migration_config


def test_populated_input_schema_survives_r1_upgrade(database_url):
    config = migration_config()
    config.attributes["database_url"] = database_url
    command.upgrade(config, "e3b311ba42f4")
    engine = create_engine(database_url)
    old = MetaData()
    identities = Table("identities", old, autoload_with=engine)
    tasks = Table("tasks", old, autoload_with=engine)
    states = Table("user_planning_state", old, autoload_with=engine)
    owner, task_id = uuid4(), uuid4()
    with engine.begin() as db:
        db.execute(
            identities.insert().values(
                id=owner,
                issuer="https://synthetic.invalid",
                subject="migration-fixture",
                name="Synthetic",
                timezone="UTC",
            )
        )
        db.execute(states.insert().values(owner_id=owner, revision=3))
        db.execute(
            tasks.insert().values(
                id=task_id,
                owner_id=owner,
                title="Preserve my task",
                remaining_minutes=75,
                priority=4,
                state="TODO",
                details={"deadline": None},
            )
        )
    command.upgrade(config, "b98ef88cd5bf")
    # The reflected pre-migration interface remains usable after the upgrade.
    with engine.begin() as db:
        row = db.execute(select(tasks).where(tasks.c.id == task_id)).mappings().one()
        assert (row["owner_id"], row["remaining_minutes"], row["details"]) == (
            owner,
            75,
            {"deadline": None},
        )
        assert db.scalar(select(states.c.revision).where(states.c.owner_id == owner)) == 3
        db.execute(tasks.update().where(tasks.c.id == task_id).values(title="Old client update"))
        assert db.scalar(select(tasks.c.title).where(tasks.c.id == task_id)) == "Old client update"
    engine.dispose()


def test_explicit_reader_marker_accepts_only_reviewed_schema_heads(migrated_database_url):
    from sqlalchemy import text

    from planner.db.session import create_db_engine, database_is_ready
    from planner.settings import Settings

    engine = create_db_engine(Settings(database_url=migrated_database_url))
    assert database_is_ready(engine, {"0014_sql_indexes"})
    assert not database_is_ready(engine, {"unreviewed_reader"})
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='unreviewed_future'"))
    assert not database_is_ready(engine, {"0014_sql_indexes"})
    engine.dispose()


def test_migration_grants_app_data_access_but_protects_schema_marker(migrated_database_url):
    from uuid import uuid4

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from planner.deployment.migrate import grant_application_access

    role = "planner_test_app_" + uuid4().hex[:16]
    admin = create_engine(migrated_database_url)
    password = "synthetic-local-only"
    try:
        grant_application_access(admin, password, role_name=role)
        url = make_url(migrated_database_url).set(username=role, password=password)
        app_engine = create_engine(url)
        try:
            with app_engine.connect() as db:
                assert db.scalar(text("SELECT count(*) FROM identities")) == 0
                assert (
                    db.scalar(
                        text(
                            "SELECT has_table_privilege(current_user,"
                            "'schema_compatibility','UPDATE')"
                        )
                    )
                    is False
                )
                assert (
                    db.scalar(text("SELECT has_table_privilege(current_user,'tasks','INSERT')"))
                    is True
                )
                assert (
                    db.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"))
                    is False
                )
        finally:
            app_engine.dispose()
    finally:
        with admin.begin() as db:
            # Test role is an internally generated identifier in this disposable database.
            if db.scalar(text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                db.exec_driver_sql('DROP OWNED BY "' + role + '"')
            db.exec_driver_sql('DROP ROLE IF EXISTS "' + role + '"')
        admin.dispose()
