"""Optional interval CP-SAT model and independently validated fallback boundary.

No arbitrary segment cap: a task has at most floor(remaining/minimum) regular
segments plus one possible final short segment, limited by physical horizon
capacity. Search budget is separate from model construction and process wall cap.
"""

from collections import defaultdict
from math import ceil
from time import perf_counter

from ortools.sat.python import cp_model

from planner.domain.contracts import Candidate, InputSnapshot, SolverMetadata, TaskState, Violation
from planner.domain.task_rules import validate_tasks
from planner.solver.diagnostics import diagnose
from planner.solver.greedy import greedy_schedule, make_block
from planner.solver.objective import SCALE, WEIGHTS, score_candidate
from planner.solver.validator import validate_candidate


def _resource_violations(snapshot):
    """Reject whole unsupported instances; never silently restrict block counts."""
    span = snapshot.horizon_end_slot - snapshot.horizon_start_slot
    capacity = max(0, min(span, sum(z - a for a, z in snapshot.availability)))
    active = [t for t in snapshot.tasks if t.state not in (TaskState.DONE, TaskState.CANCELLED)]
    segments = sum(
        min(capacity, t.required_slots) // t.min_block_slots
        + int(t.short_final_allowed and t.required_slots > 0)
        if t.splittable
        else int(t.required_slots > 0)
        for t in active
    )
    prior_count = len(snapshot.prior_candidate.blocks) if snapshot.prior_candidate else 0
    checks = [
        ("horizon_slots", span, 1440),
        ("requested_slots", sum(t.required_slots for t in active), 1_000_000),
        ("optional_intervals", segments, 20_000),
        (
            "objective_overlap_terms",
            segments * (len(snapshot.preferred_windows) + 2 * prior_count),
            100_000,
        ),
    ]
    return [
        Violation(
            code="MODEL_RESOURCE_LIMIT",
            facts={"resource": name, "estimated": value, "limit": limit},
        )
        for name, value, limit in checks
        if value > limit
    ]


def _run(model, budget_ms, seed):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = budget_ms / 1000
    solver.parameters.random_seed = seed
    solver.parameters.num_search_workers = 1
    return solver, solver.solve(model)


def _ranges(slots):
    result = []
    for i in sorted(slots):
        if result and result[-1][1] == i:
            result[-1] = (result[-1][0], i + 1)
        else:
            result.append((i, i + 1))
    return result


def build_model(snapshot: InputSnapshot, warm_start=None):
    """Return model plus extraction variables; exposed for reproducible size reports."""
    model = cp_model.CpModel()
    low, high = snapshot.horizon_start_slot, snapshot.horizon_end_slot
    span = max(0, high - low)
    available = {i for a, z in snapshot.availability for i in range(max(a, low), min(z, high))}
    for a, z in snapshot.busy_slot_ranges:
        available.difference_update(range(a, z))
    blocked = set(range(low, high)) - available
    intervals = [
        model.new_fixed_size_interval_var(a, z - a, f"busy_{a}") for a, z in _ranges(blocked)
    ]
    by_task = defaultdict(list)
    protected = defaultdict(list)
    for b in snapshot.protected_blocks:
        intervals.append(
            model.new_fixed_size_interval_var(
                b.start_slot, b.end_slot - b.start_slot, f"protected_{b.id}"
            )
        )
        protected[b.task_id].append(b)
    quantities = {}
    dynamic = {}
    active = [t for t in snapshot.tasks if t.state not in (TaskState.DONE, TaskState.CANCELLED)]
    hint = defaultdict(list)
    if warm_start:
        protected_ids = {b.id for b in snapshot.protected_blocks}
        for b in warm_start.blocks:
            if b.id not in protected_ids:
                hint[b.task_id].append(b)

    def integer(name, upper, lower=0):
        return model.new_int_var(lower, max(lower, upper), name)

    for t in active:
        name = str(t.id)
        fixed = protected[t.id]
        reserved = sum(b.end_slot - b.start_slot for b in fixed)
        remaining = max(0, t.required_slots - reserved)
        capacity = min(remaining, len(available))
        count = capacity // t.min_block_slots + int(t.short_final_allowed and capacity > 0)
        if not t.splittable:
            count = 0 if fixed else int(remaining > 0)
        segments = []
        lengths = []
        presences = []
        release = max(low, t.release_slot)
        deadline = min(high, t.deadline_slot if t.deadline_slot is not None else high)
        for j in range(count):
            p = model.new_bool_var(f"{name}_present_{j}")
            start = integer(f"{name}_start_{j}", high, low)
            end = integer(f"{name}_end_{j}", high, low)
            length = integer(f"{name}_size_{j}", min(t.max_block_slots, capacity))
            model.add(length >= 1).only_enforce_if(p)
            model.add(length == 0).only_enforce_if(p.Not())
            model.add(start == low).only_enforce_if(p.Not())
            model.add(end == low).only_enforce_if(p.Not())
            model.add(start >= release).only_enforce_if(p)
            model.add(end <= deadline).only_enforce_if(p)
            if not t.splittable:
                model.add(length == t.required_slots).only_enforce_if(p)
                if not t.short_final_allowed:
                    model.add(length >= t.min_block_slots).only_enforce_if(p)
            elif not t.short_final_allowed:
                model.add(length >= t.min_block_slots).only_enforce_if(p)
            intervals.append(
                model.new_optional_interval_var(start, length, end, p, f"{name}_interval_{j}")
            )
            if segments:
                previous = segments[-1]
                model.add(p <= previous[3])
                model.add(start >= previous[1]).only_enforce_if(p)
            segments.append((start, end, length, p))
            by_task[t.id].append((start, end))
            lengths.append(length)
            presences.append(p)
            if j < len(hint[t.id]):
                b = hint[t.id][j]
                for var, value in (
                    (p, 1),
                    (start, b.start_slot),
                    (end, b.end_slot),
                    (length, b.end_slot - b.start_slot),
                ):
                    model.add_hint(var, value)
            elif warm_start:
                for var, value in ((p, 0), (start, low), (end, low), (length, 0)):
                    model.add_hint(var, value)
        by_task[t.id].extend((b.start_slot, b.end_slot) for b in fixed)
        total = integer(f"{name}_allocated", max(t.required_slots, reserved))
        model.add(total == sum(lengths) + reserved)
        model.add(total <= t.required_slots)
        complete = model.new_bool_var(f"{name}_complete")
        model.add(total == t.required_slots).only_enforce_if(complete)
        model.add(total < t.required_slots).only_enforce_if(complete.Not())
        present = model.new_bool_var(f"{name}_scheduled")
        model.add(total > 0).only_enforce_if(present)
        model.add(total == 0).only_enforce_if(present.Not())
        if t.deadline_slot is not None and t.deadline_slot <= high:
            model.add(complete == 1)
        finish = integer(f"{name}_finish", high, low)
        model.add_max_equality(finish, [end for _, end in by_task[t.id]] or [low])
        block_count = integer(f"{name}_blocks", count + len(fixed))
        model.add(block_count == sum(presences) + len(fixed))
        if not t.splittable:
            model.add(block_count <= 1)
            model.add(complete == 1).only_enforce_if(present)
        if t.short_final_allowed:
            for j, (_, end, length, p) in enumerate(segments):
                short = model.new_bool_var(f"{name}_short_{j}")
                model.add(length < t.min_block_slots).only_enforce_if(short)
                model.add(length >= t.min_block_slots).only_enforce_if(short.Not())
                model.add(end == finish).only_enforce_if([short, p])
                model.add(complete == 1).only_enforce_if([short, p])
        for b in fixed:
            length = b.end_slot - b.start_slot
            model.add(b.start_slot >= release)
            model.add(b.end_slot <= deadline)
            if b.source != "IN_PROGRESS":
                model.add(length <= t.max_block_slots)
                if length < t.min_block_slots:
                    if t.short_final_allowed:
                        model.add(finish == b.end_slot)
                        model.add(complete == 1)
                    else:
                        model.add(False)
        dynamic[t.id] = segments
        quantities[t.id] = (total, complete, present, finish, block_count)
    model.add_no_overlap(intervals)
    tasks = {t.id: t for t in snapshot.tasks}
    for e in snapshot.dependencies:
        if tasks[e.predecessor_id].state == TaskState.DONE or e.successor_id not in quantities:
            continue
        if e.predecessor_id not in quantities:
            model.add(quantities[e.successor_id][2] == 0)
            continue
        _, complete, _, finish, _ = quantities[e.predecessor_id]
        model.add(complete == 1).only_enforce_if(quantities[e.successor_id][2])
        for start, _, _, present in dynamic[e.successor_id]:
            model.add(start >= finish).only_enforce_if(present)
        for b in protected[e.successor_id]:
            model.add(b.start_slot >= finish)

    def ratio(numerator, denominator, bound, name):
        safe = integer(name + "_denominator", max(1, bound), 1)
        model.add_max_equality(safe, [denominator, 1])
        result = integer(name, SCALE)
        model.add_division_equality(result, numerator * SCALE, safe)
        return result

    def overlap(start, end, a, z, name):
        left = integer(name + "_left", max(high, a), min(low, a))
        right = integer(name + "_right", max(high, z), min(low, z))
        model.add_max_equality(left, [start, a])
        model.add_min_equality(right, [end, z])
        result = integer(name, max(0, z - a))
        model.add_max_equality(result, [0, right - left])
        return result

    future = [t for t in active if t.deadline_slot is None or t.deadline_slot > high]
    request = sum(t.priority * t.required_slots for t in future)
    deficit = sum(t.priority * (t.required_slots - quantities[t.id][0]) for t in future)
    deficit_score = ratio(deficit, request, request, "future_deficit")
    prior = defaultdict(dict)
    cutoff = ceil((snapshot.reference_now - snapshot.slot_origin).total_seconds() / 900)
    if snapshot.prior_candidate:
        for b in snapshot.prior_candidate.blocks:
            if not b.locked:
                start = ceil((b.start - snapshot.slot_origin).total_seconds() / 900)
                end = int((b.end - snapshot.slot_origin).total_seconds() // 900)
                for i in range(max(cutoff, start), end):
                    prior[b.task_id][i] = 2 if i < cutoff + 96 else 1
    reference = sum(sum(value.values()) for value in prior.values())
    retained = []
    for task_id, slots in prior.items():
        for weight in (1, 2):
            for a, z in _ranges({i for i, w in slots.items() if w == weight}):
                for j, (start, end) in enumerate(by_task[task_id]):
                    retained.append(weight * overlap(start, end, a, z, f"retain_{task_id}_{j}_{a}"))
    disruption = ratio(reference - sum(retained), reference, reference, "disruption")
    all_allocated = sum(q[0] for q in quantities.values())
    preferred = []
    preferred_ranges = _ranges({i for a, z in snapshot.preferred_windows for i in range(a, z)})
    for task_id, segments in by_task.items():
        for j, (start, end) in enumerate(segments):
            for a, z in preferred_ranges:
                preferred.append(overlap(start, end, a, z, f"prefer_{task_id}_{j}_{a}"))
    mismatch = (
        ratio(all_allocated - sum(preferred), all_allocated, span, "preference")
        if snapshot.preferred_windows
        else model.new_constant(0)
    )
    excess = []
    max_excess = []
    positions = []
    weights = []
    for t in active:
        total, _, present, finish, blocks = quantities[t.id]
        minimum = integer(f"{t.id}_minimum_blocks", max(t.required_slots, 1))
        if t.splittable:
            model.add_division_equality(minimum, total + t.max_block_slots - 1, t.max_block_slots)
        else:
            model.add(minimum == present)
        extra = integer(f"{t.id}_extra_blocks", max(t.required_slots, 1))
        model.add_max_equality(extra, [0, blocks - minimum])
        excess.append(extra)
        max_excess.append(total - minimum)
        begin = max(low, t.release_slot)
        end = min(high, t.deadline_slot if t.deadline_slot is not None else high)
        raw = integer(
            f"{t.id}_position_raw", SCALE * max(span, 1), -SCALE * max(abs(begin - low), 1)
        )
        # For absent tasks, ignore the arbitrary finish variable.
        model.add_division_equality(raw, (finish - begin) * SCALE, max(1, end - begin))
        clipped = integer(f"{t.id}_position_clip", SCALE * max(span, 1))
        model.add_max_equality(clipped, [0, raw])
        position = integer(f"{t.id}_position", SCALE)
        model.add_min_equality(position, [SCALE, clipped])
        selected = integer(f"{t.id}_position_selected", SCALE)
        model.add(selected == position).only_enforce_if(present)
        model.add(selected == 0).only_enforce_if(present.Not())
        positions.append(t.priority * selected)
        weights.append(t.priority * present)
    fragment = ratio(sum(excess), sum(max_excess), span, "fragmentation")
    safe_weight = integer("completion_weight", max(1, sum(t.priority for t in active)), 1)
    model.add_max_equality(safe_weight, [1, sum(weights)])
    delay = integer("completion_delay", SCALE)
    model.add_division_equality(delay, sum(positions), safe_weight)
    components = (deficit_score, disruption, mismatch, fragment, delay)
    model.minimize(sum(w * c for w, c in zip(WEIGHTS, components, strict=True)))
    return model, dynamic


def solve_cp_sat(
    snapshot: InputSnapshot,
    budget_ms: int = 2000,
    seed: int = 7,
    *,
    warm_candidate: Candidate | None = None,
    use_greedy_hint: bool = True,
    allow_greedy_fallback: bool = True,
) -> Candidate:
    """budget_ms caps native solving; runtime_ms includes validation and model construction.

    Cold benchmarks disable both greedy flags. A supplied warm candidate avoids
    recomputing it and is independently validated before hinting or fallback.
    """
    started = perf_counter()
    if budget_ms < 0:
        raise ValueError("budget_ms must be nonnegative")
    base = Candidate(
        snapshot_hash=snapshot.snapshot_hash,
        planning_revision=snapshot.planning_revision,
        status="UNKNOWN",
        source_policy="CP_SAT",
    )
    invalid = validate_tasks(snapshot)
    invalid.extend(_resource_violations(snapshot))
    if snapshot.objective_version != "v1":
        invalid.append(Violation(code="OBJECTIVE_VERSION"))
    if invalid:
        return base.model_copy(
            update={"status": "MODEL_INVALID", "constraint_report": tuple(invalid)}
        )
    diagnostic = diagnose(snapshot)
    if diagnostic:
        return base.model_copy(
            update={
                "status": "INFEASIBLE",
                "constraint_report": tuple(diagnostic),
                "solver_metadata": SolverMetadata(
                    budget_ms=budget_ms,
                    seed=seed,
                    runtime_ms=(perf_counter() - started) * 1000,
                    reason_code="NECESSARY_CONDITION",
                ),
            }
        )
    greedy = warm_candidate
    if greedy is None and (use_greedy_hint or allow_greedy_fallback):
        greedy = greedy_schedule(snapshot)
    valid_greedy = (
        greedy is not None
        and greedy.status in ("FEASIBLE", "OPTIMAL")
        and not validate_candidate(snapshot, greedy)
    )
    model, variables = build_model(snapshot, greedy if valid_greedy and use_greedy_hint else None)
    solver, status = _run(model, budget_ms, seed)
    status_name = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }[status]
    metadata = SolverMetadata(
        runtime_ms=(perf_counter() - started) * 1000,
        budget_ms=budget_ms,
        seed=seed,
        variable_count=len(model.proto.variables),
        constraint_count=len(model.proto.constraints),
        reason_code="CP_" + status_name,
    )
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        blocks = list(snapshot.protected_blocks)
        for task in snapshot.tasks:
            for start, end, _, present in variables.get(task.id, ()):
                if solver.value(present):
                    blocks.append(
                        make_block(
                            snapshot, task, solver.value(start), solver.value(end), source="CP_SAT"
                        )
                    )
        result = base.model_copy(
            update={
                "status": status_name,
                "solver_metadata": metadata,
                "blocks": tuple(sorted(blocks, key=lambda b: (b.start_slot, str(b.id)))),
            }
        )
        violations = validate_candidate(snapshot, result)
        if not violations:
            return result.model_copy(update={"score": score_candidate(snapshot, result)})
        status_name = "MODEL_INVALID"
        metadata = metadata.model_copy(update={"reason_code": "VALIDATOR_REJECTED"})
    else:
        violations = []
    if allow_greedy_fallback and valid_greedy and status_name in ("UNKNOWN", "MODEL_INVALID"):
        return greedy.model_copy(
            update={"source_policy": "GREEDY_FALLBACK", "solver_metadata": metadata}
        )
    return base.model_copy(
        update={
            "status": status_name,
            "constraint_report": tuple(violations),
            "solver_metadata": metadata,
        }
    )
