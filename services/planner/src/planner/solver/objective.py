"""Objective v1. Components use integer floor scaling at 1/10,000 precision.

Completion positions are first scaled per task and then priority averaged. This
explicit rounding is shared with CP-SAT, so OPTIMAL refers to this finite objective.
Reference disruption counts occupied task/slot pairs, double weighted within 24h.
"""

from collections import defaultdict
from math import ceil

from planner.domain.contracts import Candidate, InputSnapshot, Score, TaskState

SCALE = 10_000
WEIGHTS = (30, 25, 20, 15, 10)


def score_candidate(snapshot: InputSnapshot, candidate: Candidate) -> Score:
    if snapshot.objective_version != "v1":
        raise ValueError("OBJECTIVE_VERSION: unsupported objective")
    grouped = defaultdict(list)
    for b in candidate.blocks:
        grouped[b.task_id].append(b)
    active = [t for t in snapshot.tasks if t.state not in (TaskState.DONE, TaskState.CANCELLED)]
    allocated = {t.id: sum(b.end_slot - b.start_slot for b in grouped[t.id]) for t in active}
    future = [
        t for t in active if t.deadline_slot is None or t.deadline_slot > snapshot.horizon_end_slot
    ]
    requested = sum(t.priority * t.required_slots for t in future)
    deficit = sum(t.priority * max(0, t.required_slots - allocated[t.id]) for t in future)
    slots = {(b.task_id, i) for b in candidate.blocks for i in range(b.start_slot, b.end_slot)}
    prior = {}
    cutoff = ceil((snapshot.reference_now - snapshot.slot_origin).total_seconds() / 900)
    near_end = cutoff + 96
    if snapshot.prior_candidate:
        for b in snapshot.prior_candidate.blocks:
            if not b.locked:
                # Prior integer indices belong to that snapshot's UTC midnight.
                start = ceil((b.start - snapshot.slot_origin).total_seconds() / 900)
                end = int((b.end - snapshot.slot_origin).total_seconds() // 900)
                for i in range(max(cutoff, start), end):
                    prior[(b.task_id, i)] = 2 if i < near_end else 1
    displaced = sum(weight for pair, weight in prior.items() if pair not in slots)
    reference = sum(prior.values())
    mismatch = sum(not any(a <= i < z for a, z in snapshot.preferred_windows) for _, i in slots)
    total = sum(allocated.values())
    excess = maximum_excess = 0
    completion_sum = completion_weight = 0
    for t in active:
        n = allocated[t.id]
        if not n:
            continue
        minimum = ceil(n / t.max_block_slots) if t.splittable else 1
        excess += max(0, len(grouped[t.id]) - minimum)
        maximum_excess += max(0, n - minimum)
        start = max(snapshot.horizon_start_slot, t.release_slot)
        end = min(
            snapshot.horizon_end_slot,
            t.deadline_slot if t.deadline_slot is not None else snapshot.horizon_end_slot,
        )
        finish = max(b.end_slot for b in grouped[t.id])
        position = min(SCALE, max(0, (finish - start) * SCALE // max(1, end - start)))
        completion_sum += t.priority * position
        completion_weight += t.priority

    def ratio(n, d):
        return min(SCALE, max(0, n * SCALE // d)) / SCALE if d else 0

    return Score(
        future_work_deficit=ratio(deficit, requested),
        disruption=ratio(displaced, reference),
        preference_mismatch=ratio(mismatch, total) if snapshot.preferred_windows else 0,
        fragmentation=ratio(excess, maximum_excess),
        completion_delay=(completion_sum // completion_weight) / SCALE if completion_weight else 0,
    )


def integer_penalty(score: Score) -> int:
    return round(score.total_penalty * SCALE)
