"""Local synthetic demonstration data, attached only to real signed-in fixture identities."""

from datetime import UTC, datetime, time, timedelta
from uuid import uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.db.models import Availability, Identity, PlanningState, Task
from planner.domain.commands import execute_command


def seed_demo(engine, config) -> int:
    if config.environment != "local" or config.oidc_issuer != (
        "http://127.0.0.1:28080/realms/adaptive-planner"
    ):
        raise ValueError("Demo seeding is restricted to the default local fixture realm.")
    with Session(engine) as db:
        owners = db.scalars(
            select(Identity).where(
                Identity.issuer == config.oidc_issuer, Identity.name.in_(["Demo A", "Demo B"])
            )
        ).all()
        if len(owners) != 2 or {item.name for item in owners} != {"Demo A", "Demo B"}:
            raise ValueError("Sign in once as demo-a and demo-b before running seed-demo.")
        owner_ids = [owner.id for owner in owners]

    def clock():
        return datetime.now(UTC)

    now = clock()
    date = now.date() + timedelta(days=1)
    start = datetime.combine(date, time(9), UTC).isoformat()
    end = datetime.combine(date, time(17), UTC).isoformat()
    created = 0
    for owner_id in owner_ids:
        task_ids = [uuid5(owner_id, "demo-v1-draft"), uuid5(owner_id, "demo-v1-review")]
        with Session(engine) as db:
            existing = set(
                db.scalars(
                    select(Task.id).where(Task.owner_id == owner_id, Task.id.in_(task_ids))
                ).all()
            )
            revision = db.get(PlanningState, owner_id).revision
        if existing == set(task_ids):
            continue
        if existing:
            raise ValueError("Partial demo data exists; preserve it and resolve it manually.")

        def mutate(db, owner_id=owner_id, task_ids=task_ids):
            for task_id, title in zip(
                task_ids, ("Write synthetic draft", "Review synthetic draft"), strict=True
            ):
                db.add(
                    Task(
                        id=task_id,
                        owner_id=owner_id,
                        title=title,
                        remaining_minutes=60,
                        priority=3,
                        state="TODO",
                        details={
                            "release_at": start,
                            "deadline": {"kind": "TIMESTAMP", "value": end, "timezone": "UTC"},
                            "splittable": True,
                            "min_block_slots": 2,
                            "max_block_slots": 12,
                            "short_final_allowed": False,
                        },
                    )
                )
            if db.get(Availability, owner_id) is None:
                db.add(Availability(owner_id=owner_id, windows=[{"start": start, "end": end}]))
            return {"seeded_tasks": 2}

        execute_command(
            engine,
            owner_id,
            "seed-demo",
            "demo-v1",
            {"expected_revision": revision, "fixture_version": 1},
            clock,
            mutate,
        )
        created += 1
    return created
