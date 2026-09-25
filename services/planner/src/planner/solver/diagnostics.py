"""Cheap necessary-condition failures; no heuristic-failure infeasibility claims."""

from planner.domain.contracts import InputSnapshot, TaskState, Violation
from planner.domain.task_rules import validate_tasks


def diagnose(snapshot: InputSnapshot) -> list[Violation]:
    errors = validate_tasks(snapshot)
    if errors:
        return errors
    free = {
        i
        for a, z in snapshot.availability
        for i in range(a, z)
        if snapshot.horizon_start_slot <= i < snapshot.horizon_end_slot
    }
    for a, z in snapshot.busy_slot_ranges:
        free.difference_update(range(a, z))
    required = [
        t
        for t in snapshot.tasks
        if t.state not in (TaskState.DONE, TaskState.CANCELLED)
        and t.deadline_slot is not None
        and t.deadline_slot <= snapshot.horizon_end_slot
    ]
    for deadline in sorted({t.deadline_slot for t in required}):
        due = [t for t in required if t.deadline_slot <= deadline]
        effort = sum(t.required_slots for t in due)
        capacity = sum(i < deadline for i in free)
        if effort > capacity:
            errors.append(
                Violation(
                    code="CAPACITY_BEFORE_DEADLINE",
                    related_ids=tuple(t.id for t in due),
                    facts={
                        "deadline_slot": deadline,
                        "required_slots": effort,
                        "available_slots": capacity,
                        "proof": "necessary_condition",
                    },
                )
            )
    for task in required:
        if task.splittable or not task.required_slots:
            continue
        possible = sorted(i for i in free if task.release_slot <= i < task.deadline_slot)
        run = longest = 0
        last = None
        for i in possible:
            run = run + 1 if last is not None and i == last + 1 else 1
            longest = max(longest, run)
            last = i
        if longest < task.required_slots or task.required_slots > task.max_block_slots:
            errors.append(
                Violation(
                    code="NO_CONTIGUOUS_WINDOW",
                    related_ids=(task.id,),
                    facts={
                        "required_slots": task.required_slots,
                        "longest_window_slots": longest,
                        "proof": "necessary_condition",
                    },
                )
            )
    return errors
