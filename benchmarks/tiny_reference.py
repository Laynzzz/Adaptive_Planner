"""Exhaustive tiny schedule reference. Enumerates interval subsets, not solver choices.

Bounded explicitly to eight slots / three tasks for an executable proof oracle.
It intentionally retains validator-independent enumeration of all interval sets.
"""

from itertools import product

from planner.domain.contracts import Candidate, TaskState
from planner.solver.greedy import make_block
from planner.solver.objective import score_candidate


def reference_accepts(snapshot, blocks):
    """Separate small-instance predicate; no validator or model-builder calls."""
    tasks = {t.id: t for t in snapshot.tasks}
    occupied = set()
    grouped = {t.id: [] for t in snapshot.tasks}
    for b in blocks:
        task = tasks.get(b.task_id)
        if task is None or b.owner_id != snapshot.owner_id or task.owner_id != b.owner_id:
            return False
        if task.state in (TaskState.DONE, TaskState.CANCELLED):
            return False
        if b.start_slot < max(snapshot.horizon_start_slot, task.release_slot):
            return False
        if b.end_slot > min(
            snapshot.horizon_end_slot,
            task.deadline_slot if task.deadline_slot is not None else snapshot.horizon_end_slot,
        ):
            return False
        for i in range(b.start_slot, b.end_slot):
            if i in occupied:
                return False
            if not any(a <= i < z for a, z in snapshot.availability):
                return False
            if any(a <= i < z for a, z in snapshot.busy_slot_ranges):
                return False
            occupied.add(i)
        grouped[task.id].append(b)
    for fixed in snapshot.protected_blocks:
        if fixed not in blocks:
            return False
    for task in snapshot.tasks:
        work = sorted(grouped[task.id], key=lambda b: b.start_slot)
        amount = sum(b.end_slot - b.start_slot for b in work)
        if amount > task.required_slots:
            return False
        if (
            task.state not in (TaskState.DONE, TaskState.CANCELLED)
            and task.deadline_slot is not None
            and task.deadline_slot <= snapshot.horizon_end_slot
            and amount != task.required_slots
        ):
            return False
        if work and not task.splittable and (len(work) != 1 or amount != task.required_slots):
            return False
        for i, b in enumerate(work):
            if b in snapshot.protected_blocks and b.source == "IN_PROGRESS":
                continue
            size = b.end_slot - b.start_slot
            if size > task.max_block_slots:
                return False
            if size < task.min_block_slots and not (
                task.short_final_allowed and i == len(work) - 1 and amount == task.required_slots
            ):
                return False
    for edge in snapshot.dependencies:
        pre, post = tasks[edge.predecessor_id], grouped[edge.successor_id]
        if not post or pre.state == TaskState.DONE:
            continue
        previous = grouped[pre.id]
        if pre.state == TaskState.CANCELLED:
            return False
        if sum(b.end_slot - b.start_slot for b in previous) != pre.required_slots:
            return False
        finish = max((b.end_slot for b in previous), default=snapshot.horizon_start_slot)
        if any(b.start_slot < finish for b in post):
            return False
    return True


def enumerate_candidates(snapshot):
    low, high = snapshot.horizon_start_slot, snapshot.horizon_end_slot
    active = [t for t in snapshot.tasks if t.state not in (TaskState.DONE, TaskState.CANCELLED)]
    if high - low > 8 or len(active) > 3:
        raise ValueError("tiny reference is limited to eight slots and three active tasks")
    choices = []
    for t in active:
        fixed = [b for b in snapshot.protected_blocks if b.task_id == t.id]
        room = t.required_slots - sum(b.end_slot - b.start_slot for b in fixed)
        options = []

        def visit(cursor, remaining, chosen, options=options, fixed=fixed, t=t):
            options.append(tuple(fixed + chosen))
            if not t.splittable and chosen:
                return
            for start in range(cursor, high):
                for end in range(start + 1, min(high, start + remaining) + 1):
                    visit(
                        end,
                        remaining - (end - start),
                        chosen + [make_block(snapshot, t, start, end, "EXHAUSTIVE")],
                    )

        visit(low, max(0, room), [])
        choices.append(options)
    for groups in product(*choices):
        blocks = tuple(b for group in groups for b in group)
        c = Candidate(
            snapshot_hash=snapshot.snapshot_hash,
            planning_revision=snapshot.planning_revision,
            status="FEASIBLE",
            source_policy="EXHAUSTIVE",
            blocks=blocks,
        )
        if reference_accepts(snapshot, blocks):
            yield c.model_copy(update={"score": score_candidate(snapshot, c)})


def size_smoke():
    """Single-run synthetic measurements, not percentiles or production capacity."""
    import hashlib
    import json
    import platform
    from datetime import UTC, datetime, timedelta
    from time import perf_counter
    from uuid import UUID

    import ortools

    from planner.domain.contracts import InputSnapshot, TaskSpec
    from planner.solver.cp_sat import build_model, solve_cp_sat
    from planner.solver.greedy import greedy_schedule
    from planner.solver.validator import validate_candidate

    origin = datetime(2026, 9, 25, tzinfo=UTC)
    owner = UUID(int=1)
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "ortools": ortools.__version__,
                "seed": 7,
                "cp_budget_ms": 2000,
                "cp_workers": 1,
            }
        )
    )
    for count in (20, 50, 100, 200):
        s = InputSnapshot(
            id=UUID(int=2),
            snapshot_hash="synthetic",
            owner_id=owner,
            planning_revision=1,
            reference_now=origin,
            timezone="UTC",
            slot_origin=origin,
            horizon_start=origin,
            horizon_end=origin + timedelta(days=14),
            horizon_start_slot=0,
            horizon_end_slot=1344,
            availability=((0, 1344),),
            tasks=tuple(
                TaskSpec(
                    id=UUID(int=100 + i),
                    owner_id=owner,
                    title=f"Synthetic {i}",
                    remaining_minutes=60,
                    deadline_slot=1344,
                    min_block_slots=2,
                    max_block_slots=4,
                )
                for i in range(count)
            ),
        )
        fixture_hash = hashlib.sha256(s.model_dump_json().encode()).hexdigest()
        start = perf_counter()
        model, _ = build_model(s, greedy_schedule(s))
        build_ms = (perf_counter() - start) * 1000
        start = perf_counter()
        c = solve_cp_sat(s, 2000, 7)
        wall_ms = (perf_counter() - start) * 1000
        print(
            json.dumps(
                {
                    "tasks": count,
                    "fixture_sha256": fixture_hash,
                    "variables": len(model.proto.variables),
                    "constraints": len(model.proto.constraints),
                    "build_ms": round(build_ms, 2),
                    "pipeline_ms": round(wall_ms, 2),
                    "status": c.status,
                    "policy": c.source_policy,
                    "cp_reason": c.solver_metadata.reason_code,
                    "invalid_count": len(validate_candidate(s, c)),
                    "penalty": c.score.total_penalty if c.score else None,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    size_smoke()
