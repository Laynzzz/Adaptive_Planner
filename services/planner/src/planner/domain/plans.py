"""Selection of a plan is a current-revision, current-time transaction."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from planner.db.job_models import ProposalRecord, PublicationOperation, SnapshotRecord
from planner.db.models import AuditEvent, PlanningState
from planner.domain.contracts import Candidate, InputSnapshot
from planner.jobs.coalescing import enqueue_in_transaction
from planner.solver.validator import validate_candidate


@dataclass(frozen=True)
class ActivationResult:
    code: str
    proposal_id: UUID | None = None
    publication_state: str | None = None


def activate_in_transaction(
    db: Session, owner_id: UUID, proposal_id: UUID, *, expected_revision: int, now: datetime
) -> ActivationResult:
    state = db.scalar(
        select(PlanningState).where(PlanningState.owner_id == owner_id).with_for_update()
    )
    proposal = db.scalar(
        select(ProposalRecord)
        .where(ProposalRecord.id == proposal_id, ProposalRecord.owner_id == owner_id)
        .with_for_update()
    )
    if state is None or proposal is None:
        return ActivationResult("NOT_FOUND")
    if (
        state.revision != expected_revision
        or proposal.planning_revision != state.revision
        or proposal.calendar_revision != state.calendar_revision
        or proposal.state == "SUPERSEDED"
    ):
        proposal.state = "SUPERSEDED"
        enqueue_in_transaction(db, owner_id, now=now)
        return ActivationResult("STALE_REVISION")
    stored = db.get(SnapshotRecord, proposal.snapshot_id)
    snapshot = InputSnapshot.model_validate(stored.payload)
    candidate = Candidate.model_validate(proposal.candidate)
    if candidate.snapshot_hash != stored.snapshot_hash:
        return ActivationResult("SNAPSHOT_MISMATCH")
    if candidate.status not in ("FEASIBLE", "OPTIMAL") or validate_candidate(snapshot, candidate):
        return ActivationResult("INVALID_CANDIDATE")
    if any(block.start < now for block in candidate.blocks):
        enqueue_in_transaction(db, owner_id, now=now)
        return ActivationResult("CURRENT_TIME_CONFLICT")
    if proposal.activated_at is None:
        db.execute(
            update(ProposalRecord)
            .where(
                ProposalRecord.owner_id == owner_id,
                ProposalRecord.state == "ACTIVE",
                ProposalRecord.id != proposal.id,
            )
            .values(state="SUPERSEDED")
        )
        state.active_proposal_id = proposal.id
        proposal.activated_at = now
        proposal.state = "ACTIVE"
        proposal.publication_state = "PENDING_CONNECTION"
        db.add(
            AuditEvent(
                owner_id=owner_id,
                operation="proposal.activate",
                revision=state.revision,
                occurred_at=now,
            )
        )
        for block in candidate.blocks:
            db.add(
                PublicationOperation(
                    owner_id=owner_id, proposal_id=proposal.id, block_id=block.id, created_at=now
                )
            )
    return ActivationResult("ACTIVATED", proposal.id, proposal.publication_state)


def activate_proposal(
    engine, owner_id: UUID, proposal_id: UUID, *, expected_revision: int, now: datetime
) -> ActivationResult:
    with Session(engine) as db, db.begin():
        return activate_in_transaction(
            db, owner_id, proposal_id, expected_revision=expected_revision, now=now
        )
