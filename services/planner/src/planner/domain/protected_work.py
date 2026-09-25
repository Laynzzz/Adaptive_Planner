"""Explicit protected inputs are separate from immutable proposal history."""

from datetime import timedelta

from sqlalchemy import select

from planner.api.errors import APIError
from planner.db.adaptation_models import ProtectedWork
from planner.db.job_models import ProposalRecord
from planner.db.models import PlanningState, Task
from planner.domain.contracts import Candidate
from planner.domain.task_rules import validate_tasks
from planner.jobs.dispatcher import capture_snapshot


def selected_block(db, owner_id, block_id):
    state = db.get(PlanningState, owner_id)
    proposal = db.scalar(
        select(ProposalRecord).where(
            ProposalRecord.id == state.active_proposal_id, ProposalRecord.owner_id == owner_id
        )
    )
    if proposal:
        for block in Candidate.model_validate(proposal.candidate).blocks:
            if block.id == block_id:
                return proposal, block
    raise APIError("NOT_FOUND", 404, "Selected block not found.")


def protect_block(
    db,
    owner_id,
    block_id,
    now,
    *,
    locked=True,
    in_progress=False,
    expected_end=None,
    start=None,
    end=None,
):
    _, block = selected_block(db, owner_id, block_id)
    if db.get(Task, block.task_id).state in ("DONE", "CANCELLED"):
        raise APIError("TASK_INACTIVE", 409, "This task is no longer active.")
    row = db.get(ProtectedWork, (owner_id, block_id))
    if not locked and not in_progress:
        if row:
            row.active = False
        return {"id": str(block_id), "locked": False}
    start = start or block.start
    end = end or block.end
    if in_progress:
        if expected_end is None or expected_end <= now or expected_end > now + timedelta(hours=3):
            raise APIError(
                "EXPECTED_END_REQUIRED", 422, "In-progress work needs a future expected end."
            )
        start = min(start, now)
        end = expected_end
        db.get(Task, block.task_id).state = "IN_PROGRESS"
    elif start < now:
        raise APIError("BLOCK_IN_PAST", 409, "Past work cannot be moved or locked as future work.")
    if end <= start:
        raise APIError("INVALID_INTERVAL", 422, "Block end must follow start.")
    if not in_progress and any(
        value.minute % 15 or value.second or value.microsecond for value in (start, end)
    ):
        raise APIError("LOCK_NOT_GRID_ALIGNED", 422, "Choose a 15-minute grid boundary.")
    if row is None:
        row = ProtectedWork(owner_id=owner_id, id=block_id, task_id=block.task_id)
        db.add(row)
    row.start, row.end = start, end
    row.source = "IN_PROGRESS" if in_progress else "LOCKED"
    row.locked = not in_progress
    row.active = True
    db.flush()
    for violation in validate_tasks(capture_snapshot(db, owner_id, now)):
        if violation.code in ("LOCK_EXCEEDS_REMAINING", "PROTECTED_BUSY_CONFLICT") and (
            block.task_id in violation.related_ids or block.id in violation.related_ids
        ):
            raise APIError(
                violation.code, 409, "This protected work conflicts with the current inputs."
            )
    return {
        "id": str(block_id),
        "locked": row.locked,
        "start": row.start.isoformat(),
        "end": row.end.isoformat(),
        "source": row.source,
    }
