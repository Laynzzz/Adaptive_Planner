"""Shared training/serving features available before any CP search."""

from collections import Counter, deque
from dataclasses import dataclass
from math import ceil, isfinite
from statistics import mean

from planner.domain.contracts import Candidate, InputSnapshot
from planner.solver.objective import score_candidate
from planner.solver.validator import validate_candidate

FEATURE_VERSION = "routing-features-v1"
FEATURE_NAMES = (
    "task_count",
    "mandatory_count",
    "required_slots",
    "horizon_slots",
    "free_slots",
    "utilization",
    "slack_mean",
    "slack_min",
    "slack_p10",
    "dependency_count",
    "dag_depth",
    "free_interval_count",
    "free_interval_mean",
    "free_interval_max",
    "locked_fraction",
    "changed_work_fraction",
    "greedy_valid",
    "greedy_quality",
)


@dataclass(frozen=True)
class FeatureVector:
    names: tuple[str, ...]
    values: tuple[float, ...]

    def __post_init__(self):
        if self.names != FEATURE_NAMES or len(self.values) != len(FEATURE_NAMES):
            raise ValueError("FEATURE_ORDER_MISMATCH")
        if not all(isfinite(value) for value in self.values):
            raise ValueError("NONFINITE_FEATURE")

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.names, self.values, strict=True))


def build_features(snapshot: InputSnapshot, greedy: Candidate) -> FeatureVector:
    tasks = {task.id: task for task in snapshot.tasks if task.state not in ("DONE", "CANCELLED")}
    first = ceil((snapshot.horizon_start - snapshot.slot_origin).total_seconds() / 900)
    last = int((snapshot.horizon_end - snapshot.slot_origin).total_seconds() // 900)
    horizon = max(1, last - first)
    # The normalized horizon is bounded by the input contract; build disjoint free slots.
    available = {
        slot
        for start, end in snapshot.availability
        for slot in range(max(first, start), min(last, end))
    }
    busy = {
        slot
        for start, end in snapshot.busy_slot_ranges
        for slot in range(max(first, start), min(last, end))
    }
    free = available - busy
    runs = []
    previous = None
    for slot in sorted(free):
        if previous is None or slot != previous + 1:
            runs.append(1)
        else:
            runs[-1] += 1
        previous = slot
    required = sum(task.required_slots for task in tasks.values())
    slack = sorted(
        (
            sum(
                max(first, task.release_slot)
                <= slot
                < min(last, task.deadline_slot if task.deadline_slot is not None else last)
                for slot in free
            )
            - task.required_slots
        )
        / horizon
        for task in tasks.values()
    )
    incoming = dict.fromkeys(tasks, 0)
    outgoing = {key: [] for key in tasks}
    edge_count = 0
    for edge in snapshot.dependencies:
        if edge.predecessor_id in tasks and edge.successor_id in tasks:
            outgoing[edge.predecessor_id].append(edge.successor_id)
            incoming[edge.successor_id] += 1
            edge_count += 1
    queue = deque(key for key in tasks if incoming[key] == 0)
    depth = dict.fromkeys(tasks, 1)
    visited = 0
    while queue:
        key = queue.popleft()
        visited += 1
        for child in outgoing[key]:
            depth[child] = max(depth[child], depth[key] + 1)
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
    dag_depth = max(depth.values(), default=0) if visited == len(tasks) else len(tasks)
    protected_slots = sum(
        max(0, min(last, block.end_slot) - max(first, block.start_slot))
        for block in snapshot.protected_blocks
    )
    prior = Counter()
    if snapshot.prior_candidate:
        for block in snapshot.prior_candidate.blocks:
            start = ceil((block.start - snapshot.slot_origin).total_seconds() / 900)
            end = int((block.end - snapshot.slot_origin).total_seconds() // 900)
            prior[block.task_id] += max(0, min(last, end) - max(first, start))
    current = {key: task.required_slots for key, task in tasks.items()}
    keys = set(prior) | set(current)
    change_denominator = sum(max(prior.get(key, 0), current.get(key, 0)) for key in keys)
    changed = sum(abs(prior.get(key, 0) - current.get(key, 0)) for key in keys)
    valid = greedy.status in ("FEASIBLE", "OPTIMAL") and not validate_candidate(snapshot, greedy)
    quality = score_candidate(snapshot, greedy).quality if valid else 0.0
    values = (
        len(tasks),
        sum(
            task.deadline_slot is not None and task.deadline_slot <= last for task in tasks.values()
        ),
        required,
        horizon,
        len(free),
        required / max(1, len(free)),
        mean(slack) if slack else 0,
        min(slack, default=0),
        slack[max(0, ceil(len(slack) * 0.1) - 1)] if slack else 0,
        edge_count,
        dag_depth,
        len(runs),
        mean(runs) if runs else 0,
        max(runs, default=0),
        protected_slots / max(1, required),
        changed / max(1, change_denominator),
        int(valid),
        quality,
    )
    return FeatureVector(FEATURE_NAMES, tuple(float(value) for value in values))
