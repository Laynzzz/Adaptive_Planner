"""Commit results only while their owner revision and fenced lease are current."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from planner.db.adaptation_models import WhatIfRecord
from planner.db.job_models import Job, ProposalBlock, ProposalRecord, SnapshotRecord
from planner.db.models import PlanningState
from planner.domain.contracts import Candidate, InputSnapshot
from planner.jobs.coalescing import enqueue_in_transaction
from planner.jobs.leases import restore_pending
from planner.solver.block_matching import match_blocks
from planner.solver.validator import validate_candidate


@dataclass(frozen=True)
class FinishResult:
    state: str
    proposal_id: UUID | None = None
    reason_code: str | None = None


def finalize(engine, claim, candidate: Candidate, *, now: datetime) -> FinishResult:
    with Session(engine) as db, db.begin():
        state = db.scalar(
            select(PlanningState).where(PlanningState.owner_id == claim.owner_id).with_for_update()
        )
        job = db.scalar(select(Job).where(Job.id == claim.job_id).with_for_update())
        if job and job.state == "SUCCEEDED" and job.fencing_token == claim.fencing_token:
            return FinishResult(job.state, job.proposal_id)
        if (
            not job
            or job.state != "RUNNING"
            or job.fencing_token != claim.fencing_token
            or job.lease_until <= now
        ):
            return FinishResult("FENCED", reason_code="LEASE_LOST")
        if (
            job.obsolete
            or state.revision != job.planning_revision
            or state.calendar_revision != job.calendar_revision
        ):
            job.state = "SUPERSEDED"
            job.finished_at = now
            job.lease_until = None
            if job.kind == "WHAT_IF":
                db.get(WhatIfRecord, job.what_if_id).state = "SUPERSEDED"
            enqueue_in_transaction(db, job.owner_id, now=now)
            return FinishResult("SUPERSEDED", reason_code="STALE_REVISION")
        stored = db.get(SnapshotRecord, job.snapshot_id)
        snapshot = InputSnapshot.model_validate(stored.payload)
        candidate = match_blocks(
            snapshot.prior_candidate, candidate, reference_now=snapshot.reference_now
        )
        violations = (
            validate_candidate(snapshot, candidate)
            if candidate.status in ("FEASIBLE", "OPTIMAL")
            else []
        )
        job.result = candidate.model_copy(
            update={"constraint_report": tuple(violations) or candidate.constraint_report}
        ).model_dump(mode="json", exclude_computed_fields=True)
        job.lease_until = None
        job.finished_at = now
        if job.kind == "WHAT_IF":
            preview = db.get(WhatIfRecord, job.what_if_id)
            preview.candidate = job.result
            preview.state = "READY"
            job.state = (
                "FAILED"
                if violations or candidate.status not in ("FEASIBLE", "OPTIMAL")
                else "SUCCEEDED"
            )
            job.reason_code = (
                "INVALID_CANDIDATE"
                if violations
                else (candidate.status if job.state == "FAILED" else None)
            )
            return FinishResult(job.state, reason_code=job.reason_code)
        if candidate.status not in ("FEASIBLE", "OPTIMAL") or violations:
            job.state = "FAILED"
            job.reason_code = "INVALID_CANDIDATE" if violations else candidate.status
            return FinishResult("FAILED", reason_code=job.reason_code)
        db.execute(
            update(ProposalRecord)
            .where(ProposalRecord.owner_id == claim.owner_id, ProposalRecord.state == "CURRENT")
            .values(state="SUPERSEDED")
        )
        proposal = ProposalRecord(
            owner_id=claim.owner_id,
            snapshot_id=job.snapshot_id,
            planning_revision=job.planning_revision,
            calendar_revision=job.calendar_revision,
            candidate=candidate.model_dump(mode="json", exclude_computed_fields=True),
            created_at=now,
        )
        db.add(proposal)
        db.flush()
        for block in candidate.blocks:
            db.add(
                ProposalBlock(
                    owner_id=claim.owner_id,
                    proposal_id=proposal.id,
                    id=block.id,
                    task_id=block.task_id,
                    start=block.start,
                    end=block.end,
                    locked=block.locked,
                )
            )
        job.state = "SUCCEEDED"
        job.proposal_id = proposal.id
        return FinishResult("SUCCEEDED", proposal.id)


def fail_attempt(
    engine, claim, *, now: datetime, reason_code: str, retryable: bool
) -> FinishResult:
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
            return FinishResult("FENCED", reason_code="LEASE_LOST")
        job.reason_code = reason_code
        job.lease_until = None
        if retryable and job.attempts < 5:
            job.state = "RETRY_WAIT"
            jitter = 0.5 + (job.id.int % 1000) / 2000
            job.retry_at = now + timedelta(seconds=min(60, 2**job.attempts) * jitter)
            restore_pending(db, job, state, now)
        else:
            job.state = "FAILED"
            job.finished_at = now
        return FinishResult(job.state, reason_code=reason_code)
