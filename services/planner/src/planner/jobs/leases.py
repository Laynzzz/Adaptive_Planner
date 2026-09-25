"""Lease renewal and crash recovery are fenced by each claim token."""

from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from planner.db.job_models import Job
from planner.db.models import PendingReplan, PlanningState


def heartbeat(engine, claim, *, now: datetime) -> bool:
    with Session(engine) as db, db.begin():
        state = db.scalar(
            select(PlanningState).where(PlanningState.owner_id == claim.owner_id).with_for_update()
        )
        job = db.scalar(select(Job).where(Job.id == claim.job_id).with_for_update())
        if (
            not job
            or job.state != "RUNNING"
            or job.fencing_token != claim.fencing_token
            or job.lease_until <= now
        ):
            return False
        if (
            state.revision != job.planning_revision
            or state.calendar_revision != job.calendar_revision
        ):
            job.obsolete = True
            return False
        job.lease_until = now + timedelta(seconds=30)
        return True


def is_obsolete(engine, claim) -> bool:
    with Session(engine) as db:
        job = db.get(Job, claim.job_id)
        state = db.get(PlanningState, claim.owner_id)
        return (
            not job
            or job.state != "RUNNING"
            or job.fencing_token != claim.fencing_token
            or job.obsolete
            or state.revision != claim.snapshot.planning_revision
            or state.calendar_revision != claim.calendar_revision
        )


def restore_pending(db, job, state, now):
    stmt = insert(PendingReplan).values(
        owner_id=job.owner_id,
        desired_revision=state.revision,
        enqueued_at=job.created_at,
        updated_at=now,
        explicit=True,
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[PendingReplan.owner_id],
            set_={"desired_revision": state.revision, "explicit": True},
        )
    )


def reconcile_expired(engine, *, now: datetime) -> int:
    with Session(engine) as db:
        ids = db.execute(
            select(Job.id, Job.owner_id).where(
                or_(
                    (Job.state == "RUNNING") & (Job.lease_until <= now),
                    (Job.state == "RETRY_WAIT") & (Job.retry_at <= now),
                )
            )
        ).all()
    recovered = 0
    for job_id, owner_id in ids:
        with Session(engine) as db, db.begin():
            state = db.scalar(
                select(PlanningState).where(PlanningState.owner_id == owner_id).with_for_update()
            )
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.state == "RETRY_WAIT" and job.retry_at <= now:
                job.state = "QUEUED"
                restore_pending(db, job, state, now)
                recovered += 1
                continue
            if job.state != "RUNNING" or job.lease_until > now:
                continue
            job.state = "FAILED" if job.attempts >= 5 else "QUEUED"
            job.reason_code = "LEASE_EXPIRED"
            job.lease_until = None
            if job.state == "QUEUED":
                restore_pending(db, job, state, now)
            recovered += 1
    return recovered
