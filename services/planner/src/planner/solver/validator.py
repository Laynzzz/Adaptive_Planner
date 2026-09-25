"""Recompute invariants without importing either scheduler or its predicates."""

from collections import defaultdict
from datetime import timedelta
from math import ceil, floor

from planner.domain.contracts import Candidate, InputSnapshot, TaskState, Violation
from planner.domain.task_rules import validate_tasks


def validate_candidate(snapshot: InputSnapshot, candidate: Candidate) -> list[Violation]:
    errors = list(validate_tasks(snapshot))

    def report(code, *ids, **facts):
        errors.append(Violation(code=code, related_ids=tuple(ids), facts=facts))

    if (
        candidate.snapshot_hash != snapshot.snapshot_hash
        or candidate.planning_revision != snapshot.planning_revision
    ):
        report("STALE_SNAPSHOT")
    tasks = {t.id: t for t in snapshot.tasks}
    grouped = defaultdict(list)
    seen = set()
    step = timedelta(minutes=15)
    cutoff = ceil((snapshot.reference_now - snapshot.slot_origin) / step)
    protected = {b.id: b for b in snapshot.protected_blocks}
    for b in candidate.blocks:
        if b.id in seen:
            report("DUPLICATE_BLOCK_ID", b.id)
        seen.add(b.id)
        task = tasks.get(b.task_id)
        if b.owner_id != snapshot.owner_id or (task and task.owner_id != b.owner_id):
            report("BLOCK_OWNER_MISMATCH", b.id, b.task_id)
        if task is None:
            report("UNKNOWN_TASK", b.id, b.task_id)
            continue
        grouped[b.task_id].append(b)
        if task.state in (TaskState.DONE, TaskState.CANCELLED):
            report("INACTIVE_TASK", b.id, b.task_id)
        if (
            b.start != snapshot.slot_origin + b.start_slot * step
            or b.end != snapshot.slot_origin + b.end_slot * step
        ):
            report("SLOT_ROUNDING", b.id)
        if b.start_slot < cutoff or b.start < snapshot.reference_now:
            report("PAST_BLOCK", b.id)
        if b.start_slot < snapshot.horizon_start_slot or b.end_slot > snapshot.horizon_end_slot:
            report("OUTSIDE_HORIZON", b.id)
        if not all(
            any(a <= slot < end for a, end in snapshot.availability)
            for slot in range(b.start_slot, b.end_slot)
        ):
            report("OUTSIDE_AVAILABILITY", b.id)
        if any(b.start_slot < end and a < b.end_slot for a, end in snapshot.busy_slot_ranges):
            report("BUSY_OVERLAP", b.id)
        release = task.release_slot
        if task.release_at is not None:
            release = max(release, ceil((task.release_at - snapshot.slot_origin) / step))
        if b.start_slot < release:
            report("RELEASE", b.id, task.id)
        deadline = task.deadline_slot
        if task.deadline_at is not None:
            raw_due = floor((task.deadline_at - snapshot.slot_origin) / step)
            deadline = raw_due if deadline is None else min(deadline, raw_due)
        if deadline is not None and b.end_slot > deadline:
            report("DEADLINE", b.id, task.id)
    ordered = sorted(candidate.blocks, key=lambda b: (b.start_slot, b.end_slot, str(b.id)))
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            if right.start_slot >= left.end_slot:
                break
            report("OVERLAP", left.id, right.id)
    for fixed in snapshot.protected_blocks:
        actual = next((b for b in candidate.blocks if b.id == fixed.id), None)
        if actual != fixed:
            report("PROTECTED_CHANGED", fixed.id, fixed.task_id)
    for task in snapshot.tasks:
        blocks = sorted(grouped[task.id], key=lambda b: (b.start_slot, str(b.id)))
        total = sum(b.end_slot - b.start_slot for b in blocks)
        required = (task.remaining_minutes + 14) // 15
        if total > required:
            report("WORKLOAD_EXCESS", task.id, allocated=total, required=required)
        if (
            task.state not in (TaskState.DONE, TaskState.CANCELLED)
            and task.deadline_slot is not None
            and task.deadline_slot <= snapshot.horizon_end_slot
            and total < required
        ):
            report("WORKLOAD_DEFICIT", task.id, allocated=total, required=required)
        if not task.splittable and blocks and (len(blocks) != 1 or total != required):
            report("UNSPLITTABLE", task.id)
        for index, b in enumerate(blocks):
            # An in-progress reservation may be shorter than a newly allocated block.
            if b.id in protected and b.source == "IN_PROGRESS":
                continue
            length = b.end_slot - b.start_slot
            final_short = (
                task.short_final_allowed
                and index == len(blocks) - 1
                and total == required
                and length < task.min_block_slots
            )
            if length > task.max_block_slots or (length < task.min_block_slots and not final_short):
                report("BLOCK_LENGTH", b.id, task.id)
    for edge in snapshot.dependencies:
        predecessor = tasks.get(edge.predecessor_id)
        successor = grouped[edge.successor_id]
        if not predecessor or not successor or predecessor.state == TaskState.DONE:
            continue
        previous = grouped[edge.predecessor_id]
        total = sum(b.end_slot - b.start_slot for b in previous)
        finish = max((b.end_slot for b in previous), default=cutoff)
        if (
            predecessor.state == TaskState.CANCELLED
            or total != predecessor.required_slots
            or any(b.start_slot < finish for b in successor)
        ):
            report("DEPENDENCY", edge.predecessor_id, edge.successor_id)
    return errors
