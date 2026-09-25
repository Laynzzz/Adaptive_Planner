"""Owner-scoped reads shared by routes and command transactions."""

from sqlalchemy import select

from planner.api.errors import APIError
from planner.db.models import DependencyEdge, Task


def owned_task(db, owner_id, task_id):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == owner_id))
    if task is None:
        raise APIError("NOT_FOUND", 404, "Resource not found.")
    return task


def task_data(db, task, revision=0):
    predecessors = db.scalars(
        select(DependencyEdge.predecessor_id).where(
            DependencyEdge.owner_id == task.owner_id, DependencyEdge.successor_id == task.id
        )
    ).all()
    return {
        **task.details,
        "id": str(task.id),
        "owner_id": str(task.owner_id),
        "title": task.title,
        "remaining_minutes": task.remaining_minutes,
        "required_slots": (task.remaining_minutes + 14) // 15,
        "priority": task.priority,
        "state": task.state,
        "revision": revision,
        "created_at": task.created_at.isoformat(),
        "predecessor_ids": [str(item) for item in predecessors],
    }
