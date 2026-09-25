"""Short fair dispatch transactions; solving happens after the transaction closes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from planner.db.job_models import Job, OwnerDispatchState, ProposalRecord, SnapshotRecord
from planner.db.models import (
    Availability,
    DependencyEdge,
    FixedEvent,
    Identity,
    PendingReplan,
    PlanningState,
    Task,
)
from planner.domain.contracts import Candidate, InputSnapshot
from planner.domain.time_rules import normalize_time_inputs


@dataclass(frozen=True)
class Claim:
    job_id: UUID
    owner_id: UUID
    fencing_token: int
    snapshot: InputSnapshot
    calendar_revision: int


def capture_snapshot(db: Session, owner_id: UUID, now: datetime) -> InputSnapshot:
    state = db.get(PlanningState, owner_id)
    identity = db.get(Identity, owner_id)
    availability = db.get(Availability, owner_id)
    tasks = db.scalars(select(Task).where(Task.owner_id == owner_id).order_by(Task.id)).all()
    prior = db.get(ProposalRecord, state.active_proposal_id) if state.active_proposal_id else None
    raw = {
        "owner_id": owner_id,
        "timezone": identity.timezone,
        "planning_revision": state.revision,
        "tasks": [
            dict(
                t.details,
                id=t.id,
                owner_id=t.owner_id,
                title=t.title,
                state=t.state,
                remaining_minutes=t.remaining_minutes,
                priority=t.priority,
            )
            for t in tasks
        ],
        "availability": availability.windows if availability else [],
        "fixed_events": [
            event.details
            for event in db.scalars(select(FixedEvent).where(FixedEvent.owner_id == owner_id))
        ],
        "dependencies": [
            {
                "owner_id": owner_id,
                "predecessor_id": edge.predecessor_id,
                "successor_id": edge.successor_id,
            }
            for edge in db.scalars(
                select(DependencyEdge).where(DependencyEdge.owner_id == owner_id)
            )
        ],
    }
    if prior:
        raw["prior_candidate"] = Candidate.model_validate(prior.candidate)
        raw["prior_active_candidate_id"] = prior.id
        raw["protected_blocks"] = [
            b.model_dump(exclude_computed_fields=True)
            for b in raw["prior_candidate"].blocks
            if b.locked
        ]
    return normalize_time_inputs(raw, now)


def claim_next(engine, *, now: datetime, pool_size: int = 2) -> Claim | None:
    with Session(engine) as db, db.begin():
        # Serialize only the bounded claim decision, not solver work. This enforces
        # a global local-pool limit across multiple dispatcher processes.
        db.execute(text("SELECT pg_advisory_xact_lock(712901)"))
        if (
            db.scalar(select(func.count()).select_from(Job).where(Job.state == "RUNNING"))
            >= pool_size
        ):
            return None
        running = exists().where(Job.owner_id == PlanningState.owner_id, Job.state == "RUNNING")
        retry_wait = exists().where(
            Job.owner_id == PlanningState.owner_id,
            Job.state == "RETRY_WAIT",
            Job.retry_at > now,
            Job.planning_revision == PlanningState.revision,
            Job.calendar_revision == PlanningState.calendar_revision,
        )
        state = db.scalar(
            select(PlanningState)
            .join(PendingReplan, PendingReplan.owner_id == PlanningState.owner_id)
            .outerjoin(OwnerDispatchState, OwnerDispatchState.owner_id == PlanningState.owner_id)
            .where(
                ~running,
                ~retry_wait,
                or_(
                    PendingReplan.explicit,
                    PendingReplan.updated_at <= now - timedelta(milliseconds=300),
                    PendingReplan.enqueued_at <= now - timedelta(seconds=2),
                ),
            )
            .order_by(
                OwnerDispatchState.last_dispatch_at.asc().nulls_first(),
                PendingReplan.enqueued_at,
                PlanningState.owner_id,
            )
            .with_for_update(skip_locked=True, of=PlanningState)
            .limit(1)
        )
        if state is None:
            return None
        # Initialize only after acquiring this owner's state lock. A bulk insert
        # can otherwise wait on an unrelated uncommitted owner and defeat fairness.
        db.execute(
            insert(OwnerDispatchState).values(owner_id=state.owner_id).on_conflict_do_nothing()
        )
        owner = db.scalar(
            select(OwnerDispatchState)
            .where(OwnerDispatchState.owner_id == state.owner_id)
            .with_for_update(skip_locked=True)
        )
        if owner is None:
            return None
        pending = db.get(PendingReplan, owner.owner_id)
        if pending is None:
            return None
        job = db.scalar(
            select(Job)
            .where(Job.owner_id == owner.owner_id, Job.state.in_(["QUEUED", "RETRY_WAIT"]))
            .order_by(Job.created_at)
            .with_for_update()
        )
        if job is None:
            job = Job(
                owner_id=owner.owner_id,
                planning_revision=state.revision,
                created_at=pending.enqueued_at,
            )
            db.add(job)
            db.flush()
        snapshot = capture_snapshot(db, owner.owner_id, now)
        stored = SnapshotRecord(
            id=uuid4(),
            owner_id=owner.owner_id,
            snapshot_hash=snapshot.snapshot_hash,
            payload=snapshot.model_dump(mode="json", exclude_computed_fields=True),
            created_at=now,
        )
        db.add(stored)
        db.flush()
        job.snapshot_id = stored.id
        job.state = "RUNNING"
        if (
            job.planning_revision != state.revision
            or job.calendar_revision != state.calendar_revision
        ):
            job.attempts = 0
        job.planning_revision = state.revision
        job.calendar_revision = state.calendar_revision
        job.fencing_token += 1
        job.attempts += 1
        job.obsolete = False
        job.lease_until = now + timedelta(seconds=30)
        job.retry_at = None
        owner.last_dispatch_at = now
        db.delete(pending)
        return Claim(job.id, job.owner_id, job.fencing_token, snapshot, job.calendar_revision)
