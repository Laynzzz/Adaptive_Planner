"""Observed effort changes remaining work only through an explicit estimate."""

from sqlalchemy import select

from planner.api.errors import APIError
from planner.db.adaptation_models import ProtectedWork, WorkLog
from planner.db.models import PlanningState
from planner.db.repositories import owned_task
from planner.domain.contracts import TaskState
from planner.domain.task_rules import apply_work_observation, validate_tasks
from planner.jobs.dispatcher import capture_snapshot


def record_observation(db, owner_id, task_id, body, now, *, correction_of=None):
    task = owned_task(db, owner_id, task_id)
    if task.state == "CANCELLED" or (task.state == "DONE" and correction_of is None):
        raise APIError("TASK_INACTIVE", 409, "This task is no longer active.")
    snapshot = capture_snapshot(db, owner_id, now)
    spec = next(item for item in snapshot.tasks if item.id == task.id)
    if correction_of is not None and spec.state == "DONE" and not body.complete:
        spec = spec.model_copy(update={"state": TaskState.TODO})
    updated = apply_work_observation(
        spec, body.observed_minutes, body.new_remaining_minutes, body.complete
    )
    task.remaining_minutes = updated.remaining_minutes
    task.state = updated.state
    if body.complete:
        for protected in db.scalars(
            select(ProtectedWork).where(
                ProtectedWork.owner_id == owner_id, ProtectedWork.task_id == task_id
            )
        ):
            protected.active = False
    if body.block_id is not None:
        protected = db.get(ProtectedWork, (owner_id, body.block_id))
        if protected:
            protected.active = False
    db.flush()
    after = capture_snapshot(db, owner_id, now)
    for violation in validate_tasks(after):
        if violation.code == "LOCK_EXCEEDS_REMAINING" and task_id in violation.related_ids:
            raise APIError(
                violation.code,
                409,
                "Reserved work exceeds the new estimate. Unlock or correct it first.",
            )
    log = WorkLog(
        owner_id=owner_id,
        task_id=task_id,
        observed_minutes=body.observed_minutes,
        new_remaining_minutes=updated.remaining_minutes,
        complete=body.complete,
        correction_of=correction_of.id if correction_of else None,
        block_id=body.block_id,
        created_at=now,
        proposal_id=db.get(PlanningState, owner_id).active_proposal_id if body.complete else None,
    )
    if body.block_id is not None:
        from planner.domain.protected_work import selected_block

        proposal, block = selected_block(db, owner_id, body.block_id)
        if block.task_id != task_id:
            raise APIError("NOT_FOUND", 404, "Block not found.")
        log.proposal_id = proposal.id
    db.add(log)
    db.flush()
    return {
        "id": str(log.id),
        "task_id": str(task_id),
        "observed_minutes": log.observed_minutes,
        "new_remaining_minutes": log.new_remaining_minutes,
        "complete": log.complete,
        "correction_of": str(log.correction_of) if log.correction_of else None,
        "block_id": str(log.block_id) if log.block_id else None,
        "created_at": log.created_at.isoformat(),
    }
