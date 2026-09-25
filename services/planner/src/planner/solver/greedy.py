"""Deterministic earliest-window baseline; failure never proves infeasibility."""

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from planner.domain.contracts import Block, Candidate, InputSnapshot, TaskState, Violation
from planner.domain.task_rules import validate_tasks
from planner.solver.objective import score_candidate
from planner.solver.validator import validate_candidate


def make_block(snapshot, task, start, end, source="GREEDY"):
    return Block(
        id=uuid5(NAMESPACE_URL, f"{snapshot.owner_id}/{task.id}/{start}/{end}"),
        owner_id=snapshot.owner_id,
        task_id=task.id,
        start=snapshot.slot_origin + timedelta(minutes=15 * start),
        end=snapshot.slot_origin + timedelta(minutes=15 * end),
        start_slot=start,
        end_slot=end,
        source=source,
    )


def greedy_schedule(snapshot: InputSnapshot) -> Candidate:
    errors = validate_tasks(snapshot)
    base = Candidate(
        snapshot_hash=snapshot.snapshot_hash,
        planning_revision=snapshot.planning_revision,
        status="UNKNOWN",
        source_policy="GREEDY",
        blocks=snapshot.protected_blocks,
    )
    if errors or snapshot.objective_version != "v1":
        return base.model_copy(
            update={
                "status": "MODEL_INVALID",
                "constraint_report": tuple(errors) or (Violation(code="OBJECTIVE_VERSION"),),
            }
        )
    blocks = list(snapshot.protected_blocks)
    free = {
        i
        for a, z in snapshot.availability
        for i in range(a, z)
        if snapshot.horizon_start_slot <= i < snapshot.horizon_end_slot
    }
    for a, z in snapshot.busy_slot_ranges:
        free.difference_update(range(a, z))
    for b in blocks:
        free.difference_update(range(b.start_slot, b.end_slot))
    tasks = {t.id: t for t in snapshot.tasks}
    pending = {t.id for t in snapshot.tasks if t.state not in (TaskState.DONE, TaskState.CANCELLED)}
    processed = {t.id for t in snapshot.tasks if t.state == TaskState.DONE}
    while pending:
        eligible = [
            tasks[id_]
            for id_ in pending
            if all(
                e.predecessor_id in processed
                for e in snapshot.dependencies
                if e.successor_id == id_
            )
        ]
        if not eligible:
            break
        t = min(
            eligible,
            key=lambda t: (
                t.deadline_slot
                if t.deadline_slot is not None and t.deadline_slot <= snapshot.horizon_end_slot
                else snapshot.horizon_end_slot + 1,
                -t.priority,
                t.release_slot,
                str(t.id),
            ),
        )
        pending.remove(t.id)
        current = [b for b in blocks if b.task_id == t.id]
        remaining = t.required_slots - sum(b.end_slot - b.start_slot for b in current)
        release = max(snapshot.horizon_start_slot, t.release_slot)
        blocked = False
        for e in snapshot.dependencies:
            if e.successor_id != t.id or tasks[e.predecessor_id].state == TaskState.DONE:
                continue
            pred = [b for b in blocks if b.task_id == e.predecessor_id]
            if (
                sum(b.end_slot - b.start_slot for b in pred)
                != tasks[e.predecessor_id].required_slots
            ):
                blocked = True
            release = max(release, max((b.end_slot for b in pred), default=release))
        end = min(
            snapshot.horizon_end_slot,
            t.deadline_slot if t.deadline_slot is not None else snapshot.horizon_end_slot,
        )
        if not blocked and remaining > 0 and (t.splittable or not current):
            cursor = release
            while cursor < end and remaining:
                if cursor not in free:
                    cursor += 1
                    continue
                stop = cursor
                while stop < end and stop in free:
                    stop += 1
                length = min(stop - cursor, remaining, t.max_block_slots)
                if not t.splittable:
                    length = (
                        remaining
                        if stop - cursor >= remaining and remaining <= t.max_block_slots
                        else 0
                    )
                elif not t.short_final_allowed and 0 < remaining - length < t.min_block_slots:
                    length -= t.min_block_slots - (remaining - length)
                is_final = length == remaining and t.short_final_allowed
                # Protected future blocks must remain the final block if they occur later.
                if current and any(b.start_slot >= cursor + length for b in current):
                    is_final = False
                if length > 0 and (length >= t.min_block_slots or is_final):
                    b = make_block(snapshot, t, cursor, cursor + length)
                    blocks.append(b)
                    free.difference_update(range(cursor, cursor + length))
                    remaining -= length
                    cursor += length
                else:
                    cursor = stop
        processed.add(t.id)
    result = base.model_copy(
        update={"blocks": tuple(sorted(blocks, key=lambda b: (b.start_slot, str(b.id))))}
    )
    violations = validate_candidate(snapshot, result)
    return result.model_copy(
        update={
            "status": "UNKNOWN" if violations else "FEASIBLE",
            "constraint_report": tuple(violations),
            "score": score_candidate(snapshot, result) if not violations else None,
        }
    )
