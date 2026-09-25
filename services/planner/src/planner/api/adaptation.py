"""Explicit progress, protected work, and isolated what-if commands."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.api.auth import Principal, require_mutation, require_session
from planner.api.errors import APIError
from planner.api.plans import _command
from planner.api.routes import transact, validate_intervals, validate_task
from planner.api.schemas import Interval, RevisionCommand, Schema
from planner.db.adaptation_models import ProtectedWork, WhatIfRecord, WorkLog
from planner.db.job_models import Job, ProposalRecord, SnapshotRecord
from planner.db.models import Availability, Identity, PendingReplan, PlanningState
from planner.db.repositories import owned_task
from planner.domain.contracts import Candidate, Deadline, InputSnapshot, Instant, PlanDiff
from planner.domain.plan_diff import diff_plans
from planner.domain.protected_work import protect_block
from planner.domain.work_logs import record_observation
from planner.jobs.coalescing import enqueue_in_transaction
from planner.jobs.dispatcher import capture_snapshot

router = APIRouter(prefix="/api/v1", tags=["adaptation"])


class WorkCommand(RevisionCommand):
    observed_minutes: int = Field(ge=0, le=2147483647, strict=True)
    new_remaining_minutes: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    complete: bool = False
    block_id: UUID | None = None

    @model_validator(mode="after")
    def explicit_remaining(self):
        if self.new_remaining_minutes is None and not self.complete:
            raise ValueError("Supply a revised remaining estimate or mark complete.")
        if self.complete and self.new_remaining_minutes not in (None, 0):
            raise ValueError("Completion requires zero remaining work.")
        return self


class WorkLogView(Schema):
    id: UUID
    task_id: UUID
    observed_minutes: int
    new_remaining_minutes: int
    complete: bool
    correction_of: UUID | None = None
    block_id: UUID | None = None
    created_at: datetime
    revision: int | None = None


class WorkLogList(Schema):
    items: list[WorkLogView]
    revision: int


def log_view(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "task_id",
            "observed_minutes",
            "new_remaining_minutes",
            "complete",
            "correction_of",
            "block_id",
            "created_at",
        )
    }


@router.get("/tasks/{task_id}/work-logs", response_model=WorkLogList)
def history(task_id: UUID, request: Request, principal: Principal = Depends(require_session)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        owned_task(db, principal.owner_id, task_id)
        rows = db.scalars(
            select(WorkLog)
            .where(WorkLog.owner_id == principal.owner_id, WorkLog.task_id == task_id)
            .order_by(WorkLog.created_at, WorkLog.id)
        )
        return {
            "items": [log_view(row) for row in rows],
            "revision": db.get(PlanningState, principal.owner_id).revision,
        }


@router.post("/tasks/{task_id}/work-logs", response_model=WorkLogView, status_code=201)
def observe(
    task_id: UUID,
    body: WorkCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    return transact(
        request,
        principal,
        body.model_dump(mode="json"),
        lambda db: record_observation(
            db, principal.owner_id, task_id, body, request.app.state.clock()
        ),
        201,
    )


@router.post("/work-logs/{log_id}/corrections", response_model=WorkLogView, status_code=201)
def correct(
    log_id: UUID,
    body: WorkCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        row = db.scalar(
            select(WorkLog).where(WorkLog.id == log_id, WorkLog.owner_id == principal.owner_id)
        )
        if row is None:
            raise APIError("NOT_FOUND", 404, "Work log not found.")
        return record_observation(
            db, principal.owner_id, row.task_id, body, request.app.state.clock(), correction_of=row
        )

    return transact(request, principal, body.model_dump(mode="json"), mutate, 201)


class LockCommand(RevisionCommand):
    locked: bool
    in_progress: bool = False
    expected_end: Instant | None = None


class MoveCommand(RevisionCommand):
    start: Instant
    end: Instant


class ProtectedView(Schema):
    id: UUID
    locked: bool
    start: datetime | None = None
    end: datetime | None = None
    source: str | None = None
    revision: int


class ProtectedItem(Schema):
    id: UUID
    task_id: UUID
    start: datetime
    end: datetime
    locked: bool
    source: str
    active: bool


class ProtectedList(Schema):
    items: list[ProtectedItem]
    revision: int


@router.get("/protected-work", response_model=ProtectedList)
def protected_list(request: Request, principal: Principal = Depends(require_session)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        rows = db.scalars(
            select(ProtectedWork)
            .where(ProtectedWork.owner_id == principal.owner_id, ProtectedWork.active)
            .order_by(ProtectedWork.start, ProtectedWork.id)
        )
        return {
            "items": [
                {
                    key: getattr(row, key)
                    for key in ("id", "task_id", "start", "end", "locked", "source", "active")
                }
                for row in rows
            ],
            "revision": db.get(PlanningState, principal.owner_id).revision,
        }


@router.post("/blocks/{block_id}/lock", response_model=ProtectedView)
def lock(
    block_id: UUID,
    body: LockCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    return transact(
        request,
        principal,
        body.model_dump(mode="json"),
        lambda db: protect_block(
            db,
            principal.owner_id,
            block_id,
            request.app.state.clock(),
            locked=body.locked,
            in_progress=body.in_progress,
            expected_end=body.expected_end,
        ),
    )


@router.post("/blocks/{block_id}/move", response_model=ProtectedView)
def move(
    block_id: UUID,
    body: MoveCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    return transact(
        request,
        principal,
        body.model_dump(mode="json"),
        lambda db: protect_block(
            db,
            principal.owner_id,
            block_id,
            request.app.state.clock(),
            start=body.start,
            end=body.end,
        ),
    )


class TaskChange(Schema):
    task_id: UUID
    remaining_minutes: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    deadline: Deadline | None = None

    @model_validator(mode="after")
    def remaining_not_null(self):
        if "remaining_minutes" in self.model_fields_set and self.remaining_minutes is None:
            raise ValueError("Remaining minutes must be an integer.")
        return self


class WhatIfCommand(RevisionCommand):
    task_changes: list[TaskChange] = Field(default_factory=list, max_length=200)
    additional_availability: list[Interval] = Field(default_factory=list, max_length=200)


class WhatIfCreated(Schema):
    id: UUID
    job_id: UUID
    state: str


class WhatIfView(WhatIfCreated):
    base_revision: int
    candidate: Candidate | None = None
    diff: PlanDiff | None = None


def owned_preview(db, owner_id, preview_id):
    row = db.scalar(
        select(WhatIfRecord).where(WhatIfRecord.id == preview_id, WhatIfRecord.owner_id == owner_id)
    )
    if row is None:
        raise APIError("NOT_FOUND", 404, "What-if not found.")
    return row


@router.post("/what-ifs", response_model=WhatIfCreated, status_code=202)
def preview(
    body: WhatIfCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    payload = body.model_dump(mode="json", exclude_unset=True)

    def mutate(db, state, now):
        changes = {k: v for k, v in payload.items() if k != "expected_revision"}
        if len({p["task_id"] for p in changes.get("task_changes", [])}) != len(
            changes.get("task_changes", [])
        ):
            raise APIError("INVALID_INPUT", 422, "Each task may appear once.")
        try:
            snapshot = capture_snapshot(db, principal.owner_id, now, changes=changes)
        except ValueError:
            raise APIError("INVALID_INPUT", 422, "Check the proposed changes.") from None
        if db.get(PendingReplan, principal.owner_id):
            queued_preview = db.scalar(
                select(Job.id)
                .where(
                    Job.owner_id == principal.owner_id,
                    Job.kind == "WHAT_IF",
                    Job.planning_revision == state.revision,
                    Job.state.in_(["QUEUED", "RETRY_WAIT"]),
                )
                .limit(1)
            )
            # Preserve real input demand, but a second preview does not create it.
            if queued_preview is None:
                enqueue_in_transaction(db, principal.owner_id, now=now)
        else:
            db.add(
                PendingReplan(
                    owner_id=principal.owner_id,
                    desired_revision=state.revision,
                    enqueued_at=now,
                    updated_at=now,
                    explicit=True,
                )
            )
        row = WhatIfRecord(
            owner_id=principal.owner_id,
            base_revision=state.revision,
            changes=changes,
            created_at=now,
            base_candidate=snapshot.prior_candidate.model_dump(
                mode="json", exclude_computed_fields=True
            )
            if snapshot.prior_candidate
            else None,
        )
        db.add(row)
        db.flush()
        job = Job(
            owner_id=principal.owner_id,
            kind="WHAT_IF",
            what_if_id=row.id,
            planning_revision=state.revision,
            calendar_revision=state.calendar_revision,
            created_at=now,
        )
        db.add(job)
        db.flush()
        return {"id": str(row.id), "job_id": str(job.id), "state": "QUEUED"}

    return _command(request, principal, "what-ifs.create", payload, mutate, status=202)


@router.get("/what-ifs/{preview_id}", response_model=WhatIfView)
def get_preview(
    preview_id: UUID, request: Request, principal: Principal = Depends(require_session)
):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        row = owned_preview(db, principal.owner_id, preview_id)
        job = db.scalar(
            select(Job).where(Job.what_if_id == row.id, Job.owner_id == principal.owner_id)
        )
        candidate = Candidate.model_validate(row.candidate) if row.candidate else None
        old = Candidate.model_validate(row.base_candidate) if row.base_candidate else None
        return {
            "id": row.id,
            "job_id": job.id,
            "state": job.state if row.state == "QUEUED" else row.state,
            "base_revision": row.base_revision,
            "candidate": candidate,
            "diff": diff_plans(old, candidate) if old and candidate else None,
        }


class AppliedView(Schema):
    id: UUID
    state: str
    revision: int


@router.post("/what-ifs/{preview_id}/apply", response_model=AppliedView)
def apply_preview(
    preview_id: UUID,
    body: RevisionCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        row = owned_preview(db, principal.owner_id, preview_id)
        if row.base_revision != body.expected_revision:
            raise APIError("STALE_REVISION", 409, "Inputs changed since this preview.")
        if (
            row.state != "READY"
            or not row.candidate
            or row.candidate["status"] not in ("FEASIBLE", "OPTIMAL")
        ):
            raise APIError("PREVIEW_NOT_APPLICABLE", 409, "This preview cannot be applied.")
        job = db.scalar(
            select(Job).where(Job.what_if_id == row.id, Job.owner_id == principal.owner_id)
        )
        if job.state != "SUCCEEDED":
            raise APIError("PREVIEW_NOT_APPLICABLE", 409, "The preview did not pass validation.")
        for patch in row.changes.get("task_changes", []):
            task = owned_task(db, principal.owner_id, UUID(patch["task_id"]))
            if task.state in ("DONE", "CANCELLED"):
                raise APIError("TASK_INACTIVE", 409, "This task is no longer active.")
            data = {
                **task.details,
                "title": task.title,
                "priority": task.priority,
                "remaining_minutes": task.remaining_minutes,
            }
            data.update({k: v for k, v in patch.items() if k != "task_id"})
            validate_task(db, principal.owner_id, data, request.app.state.clock)
            task.remaining_minutes = data["remaining_minutes"]
            task.details = {
                k: v for k, v in data.items() if k not in ("title", "priority", "remaining_minutes")
            }
        windows = row.changes.get("additional_availability", [])
        validate_intervals(windows, db.get(Identity, principal.owner_id).timezone)
        if windows:
            availability = db.get(Availability, principal.owner_id)
            if availability is None:
                availability = Availability(owner_id=principal.owner_id, windows=[])
                db.add(availability)
            availability.windows = [*availability.windows, *windows]
        row.state = "APPLIED"
        row.applied_at = request.app.state.clock()
        return {"id": str(row.id), "state": "APPLIED"}

    return transact(request, principal, body.model_dump(mode="json"), mutate)


@router.get("/proposals/{proposal_id}/diff", response_model=PlanDiff)
def proposal_diff(
    proposal_id: UUID, request: Request, principal: Principal = Depends(require_session)
):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        row = db.scalar(
            select(ProposalRecord).where(
                ProposalRecord.id == proposal_id, ProposalRecord.owner_id == principal.owner_id
            )
        )
        if row is None:
            raise APIError("NOT_FOUND", 404, "Proposal not found.")
        snapshot = InputSnapshot.model_validate(db.get(SnapshotRecord, row.snapshot_id).payload)
        candidate = Candidate.model_validate(row.candidate)
        return (
            diff_plans(snapshot.prior_candidate, candidate)
            if snapshot.prior_candidate
            else PlanDiff(added=candidate.blocks)
        )
