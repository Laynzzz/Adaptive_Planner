"""Coalesce durable demand while preserving the first enqueue time."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from planner.db.job_models import Job, OwnerDispatchState
from planner.db.models import PendingReplan, PlanningState


def enqueue_in_transaction(db: Session, owner_id: UUID, *, now: datetime, explicit=False) -> UUID:
    state = db.scalar(
        select(PlanningState).where(PlanningState.owner_id == owner_id).with_for_update()
    )
    if state is None:
        raise ValueError("OWNER_NOT_FOUND")
    statement = insert(PendingReplan).values(
        owner_id=owner_id,
        desired_revision=state.revision,
        enqueued_at=now,
        updated_at=now,
        explicit=explicit,
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[PendingReplan.owner_id],
            set_={
                "desired_revision": state.revision,
                "updated_at": now,
                "explicit": PendingReplan.explicit | explicit,
            },
        )
    )
    db.execute(insert(OwnerDispatchState).values(owner_id=owner_id).on_conflict_do_nothing())
    db.execute(
        update(Job)
        .where(
            Job.owner_id == owner_id,
            Job.state == "RUNNING",
            Job.planning_revision != state.revision,
        )
        .values(obsolete=True)
    )
    job = db.scalar(
        select(Job)
        .where(
            Job.owner_id == owner_id, Job.kind == "REPLAN", Job.state.in_(["QUEUED", "RETRY_WAIT"])
        )
        .order_by(Job.created_at)
        .with_for_update()
    )
    if job is None:
        job = Job(owner_id=owner_id, planning_revision=state.revision, created_at=now)
        db.add(job)
        db.flush()
    else:
        if (
            job.planning_revision != state.revision
            or job.calendar_revision != state.calendar_revision
        ):
            job.attempts = 0
            job.state = "QUEUED"
            job.retry_at = None
        job.planning_revision = state.revision
        if explicit:
            job.state = "QUEUED"
            job.retry_at = None
    return job.id


def enqueue(engine, owner_id: UUID, *, now: datetime, explicit=False) -> UUID:
    with Session(engine) as db, db.begin():
        return enqueue_in_transaction(db, owner_id, now=now, explicit=explicit)
