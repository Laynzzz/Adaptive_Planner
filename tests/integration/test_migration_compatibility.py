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
