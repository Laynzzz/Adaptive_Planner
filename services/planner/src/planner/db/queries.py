"""Batch dependency projection while preserving the task page's transaction snapshot."""

from sqlalchemy import select

from planner.db.models import DependencyEdge


def task_page_data(db, tasks, revision=0):
    if not tasks:
        return []
    owner_id = tasks[0].owner_id
    if any(task.owner_id != owner_id for task in tasks):
        raise ValueError("A task page must have exactly one owner")
    predecessors = {task.id: [] for task in tasks}
    rows = db.execute(
        select(DependencyEdge.successor_id, DependencyEdge.predecessor_id)
        .where(DependencyEdge.owner_id == owner_id, DependencyEdge.successor_id.in_(predecessors))
        .order_by(DependencyEdge.predecessor_id)
    )
    for successor, predecessor in rows:
        predecessors[successor].append(str(predecessor))
    return [
        {
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
            "predecessor_ids": predecessors[task.id],
        }
        for task in tasks
    ]
