"""Owner-scoped durable replanning and explicit local activation endpoints."""

import hashlib
import json
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from planner.api.auth import Principal, require_mutation, require_session
from planner.api.errors import APIError
from planner.db.job_models import Job, ProposalRecord, SnapshotRecord
from planner.db.models import CommandReceipt, PlanningState
from planner.domain.contracts import Candidate, Contract, OriginalTimeInput, RoundingLoss
from planner.domain.plans import activate_in_transaction
from planner.jobs.coalescing import enqueue_in_transaction

router = APIRouter(prefix="/api/v1", tags=["plans"])


class RevisionCommand(Contract):
    expected_revision: int = Field(ge=0)


class GenerateResponse(Contract):
    job_id: UUID
    state: str
    planning_revision: int


class JobView(Contract):
    id: UUID
    state: str
    planning_revision: int
    proposal_id: UUID | None = None
    reason_code: str | None = None
    candidate: Candidate | None = None


class ProposalView(Contract):
    id: UUID
    state: str
    planning_revision: int
    candidate: Candidate
    publication_state: str
    activated_at: datetime | None = None


class ProposalList(Contract):
    items: tuple[ProposalView, ...]


class TimeInputView(Contract):
    timezone: str
    original_time_inputs: tuple[OriginalTimeInput, ...] = ()
    rounding_losses: tuple[RoundingLoss, ...] = ()


def time_input_view(db, snapshot_id, owner_id):
    snapshot = db.scalar(
        select(SnapshotRecord).where(
            SnapshotRecord.id == snapshot_id, SnapshotRecord.owner_id == owner_id
        )
    )
    if snapshot is None:
        raise APIError("NOT_FOUND", 404, "Planning inputs not found.")
    return TimeInputView(
        **{
            key: snapshot.payload[key]
            for key in ("timezone", "original_time_inputs", "rounding_losses")
        }
    )


@router.get("/proposals/{proposal_id}/time-inputs", response_model=TimeInputView)
def proposal_time_inputs(
    proposal_id: UUID, request: Request, principal: Principal = Depends(require_session)
):
    with Session(request.app.state.engine) as db:
        proposal = db.scalar(
            select(ProposalRecord).where(
                ProposalRecord.id == proposal_id, ProposalRecord.owner_id == principal.owner_id
            )
        )
        if proposal is None:
            raise APIError("NOT_FOUND", 404, "Proposal not found.")
        return time_input_view(db, proposal.snapshot_id, principal.owner_id)


@router.get("/jobs/{job_id}/time-inputs", response_model=TimeInputView)
def job_time_inputs(
    job_id: UUID, request: Request, principal: Principal = Depends(require_session)
):
    with Session(request.app.state.engine) as db:
        job = db.scalar(select(Job).where(Job.id == job_id, Job.owner_id == principal.owner_id))
        if job is None:
            raise APIError("NOT_FOUND", 404, "Job not found.")
        return time_input_view(db, job.snapshot_id, principal.owner_id)


class ActivationView(Contract):
    id: UUID
    state: str
    publication_state: str
    planning_revision: int


def _command(request, principal, operation, payload, mutate, status=200):
    key = request.headers.get("Idempotency-Key", "")
    if not key or len(key) > 128:
        raise APIError("IDEMPOTENCY_REQUIRED", 400, "Supply an Idempotency-Key.")
    body_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    try:
        with Session(request.app.state.engine) as db, db.begin():
            state = db.scalar(
                select(PlanningState)
                .where(PlanningState.owner_id == principal.owner_id)
                .with_for_update(nowait=True)
            )
            now = request.app.state.clock()
            receipt = db.get(CommandReceipt, (principal.owner_id, operation, key))
            if receipt and receipt.expires_at > now:
                if receipt.body_hash != body_hash:
                    raise APIError(
                        "IDEMPOTENCY_CONFLICT", 409, "This key was used for different input."
                    )
                return receipt.response
            if receipt:
                db.delete(receipt)
                db.flush()
            if state.revision != payload["expected_revision"]:
                raise APIError("STALE_REVISION", 409, "Inputs changed. Refresh before retrying.")
            response = mutate(db, state, now)
            if "code" not in response:
                db.add(
                    CommandReceipt(
                        owner_id=principal.owner_id,
                        operation=operation,
                        key=key,
                        body_hash=body_hash,
                        response=response,
                        status_code=status,
                        expires_at=now + timedelta(days=7),
                    )
                )
        if "code" in response:
            code = response["code"]
            raise APIError(
                code,
                404 if code == "NOT_FOUND" else 409,
                "The proposal cannot be selected. Refresh to inspect the current plan.",
            )
        return response
    except OperationalError as error:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            raise APIError(
                "COMMAND_IN_PROGRESS", 409, "Another command is in progress.", retryable=True
            ) from None
        raise


@router.post("/replans", response_model=GenerateResponse, status_code=202)
def generate(
    body: RevisionCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    def mutate(db, state, now):
        job_id = enqueue_in_transaction(db, principal.owner_id, now=now, explicit=True)
        return {"job_id": str(job_id), "state": "QUEUED", "planning_revision": state.revision}

    return _command(request, principal, "replans.generate", body.model_dump(), mutate, status=202)


@router.get("/jobs/{job_id}", response_model=JobView)
def get_job(job_id: UUID, request: Request, principal: Principal = Depends(require_session)):
    with Session(request.app.state.engine) as db:
        job = db.scalar(select(Job).where(Job.id == job_id, Job.owner_id == principal.owner_id))
        if job is None:
            raise APIError("NOT_FOUND", 404, "Job not found.")
        return JobView(
            id=job.id,
            state=job.state,
            planning_revision=job.planning_revision,
            proposal_id=job.proposal_id,
            reason_code=job.reason_code,
            candidate=Candidate.model_validate(job.result) if job.result else None,
        )


def proposal_view(proposal):
    return ProposalView(
        id=proposal.id,
        state=proposal.state,
        planning_revision=proposal.planning_revision,
        candidate=Candidate.model_validate(proposal.candidate),
        publication_state=proposal.publication_state,
        activated_at=proposal.activated_at,
    )


@router.get("/active-plan", response_model=ProposalView | None)
def active_plan(request: Request, principal: Principal = Depends(require_session)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        state = db.get(PlanningState, principal.owner_id)
        proposal = db.scalar(
            select(ProposalRecord).where(
                ProposalRecord.id == state.active_proposal_id,
                ProposalRecord.owner_id == principal.owner_id,
            )
        )
        return proposal_view(proposal) if proposal else None


@router.get("/proposals", response_model=ProposalList)
def list_proposals(request: Request, principal: Principal = Depends(require_session)):
    with Session(request.app.state.engine) as db:
        proposals = db.scalars(
            select(ProposalRecord)
            .where(ProposalRecord.owner_id == principal.owner_id)
            .order_by(ProposalRecord.created_at.desc(), ProposalRecord.id)
            .limit(50)
        )
        return ProposalList(items=tuple(proposal_view(item) for item in proposals))


@router.get("/proposals/{proposal_id}", response_model=ProposalView)
def get_proposal(
    proposal_id: UUID, request: Request, principal: Principal = Depends(require_session)
):
    with Session(request.app.state.engine) as db:
        proposal = db.scalar(
            select(ProposalRecord).where(
                ProposalRecord.id == proposal_id, ProposalRecord.owner_id == principal.owner_id
            )
        )
        if proposal is None:
            raise APIError("NOT_FOUND", 404, "Proposal not found.")
        return proposal_view(proposal)


@router.post("/proposals/{proposal_id}/activate", response_model=ActivationView)
def activate(
    proposal_id: UUID,
    body: RevisionCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db, state, now):
        result = activate_in_transaction(
            db, principal.owner_id, proposal_id, expected_revision=body.expected_revision, now=now
        )
        if result.code != "ACTIVATED":
            return {"code": result.code}
        return {
            "id": str(proposal_id),
            "state": "ACTIVE",
            "publication_state": result.publication_state,
            "planning_revision": state.revision,
        }

    return _command(
        request, principal, f"proposals.activate:{proposal_id}", body.model_dump(), mutate
    )
