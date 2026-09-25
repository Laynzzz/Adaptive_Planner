"""Pure task validation and explicit work-accounting transitions."""

from collections import defaultdict

from planner.domain.contracts import InputSnapshot, TaskSpec, TaskState, Violation


def validate_tasks(snapshot: InputSnapshot) -> list[Violation]:
    violations = []

    def report(code, ids=(), **facts):
        violations.append(Violation(code=code, related_ids=ids, facts=facts))

    tasks = {task.id: task for task in snapshot.tasks}
    if len(tasks) != len(snapshot.tasks):
        report("DUPLICATE_TASK_ID")
    if (
        sum(task.state not in (TaskState.DONE, TaskState.CANCELLED) for task in snapshot.tasks)
        > 200
    ):
        report("ACTIVE_TASK_LIMIT", limit=200)
    for task in snapshot.tasks:
        if task.owner_id != snapshot.owner_id:
            report("TASK_OWNER_MISMATCH", (task.id,))
        if task.state == TaskState.DONE and task.remaining_minutes:
            report("DONE_HAS_REMAINING_WORK", (task.id,))
        if task.state not in (TaskState.DONE, TaskState.CANCELLED):
            if task.deadline_at is not None and task.deadline_at < snapshot.reference_now:
                report("PAST_DEADLINE", (task.id,))
    graph = defaultdict(list)
    indegree = dict.fromkeys(tasks, 0)
    for edge in snapshot.dependencies:
        a, b = tasks.get(edge.predecessor_id), tasks.get(edge.successor_id)
        ids = (edge.predecessor_id, edge.successor_id)
        if a is None or b is None:
            report("DEPENDENCY_TASK_MISSING", ids)
            continue
        if (
            edge.owner_id != snapshot.owner_id
            or a.owner_id != b.owner_id
            or a.owner_id != snapshot.owner_id
        ):
            report("CROSS_OWNER_DEPENDENCY", ids)
        if a.state == TaskState.CANCELLED:
            report("CANCELLED_PREDECESSOR", ids)
        graph[a.id].append(b.id)
        indegree[b.id] += 1
    ready = [task_id for task_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        task_id = ready.pop()
        visited += 1
        for child in graph[task_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(tasks):
        report(
            "DEPENDENCY_CYCLE",
            tuple(sorted((key for key, value in indegree.items() if value), key=str)),
        )
    reserved = defaultdict(int)
    for block in snapshot.protected_blocks:
        task = tasks.get(block.task_id)
        if task is None:
            report("PROTECTED_TASK_MISSING", (block.id, block.task_id))
            continue
        if block.owner_id != snapshot.owner_id or task.owner_id != block.owner_id:
            report("PROTECTED_OWNER_MISMATCH", (block.id, task.id))
        if task.state in (TaskState.DONE, TaskState.CANCELLED):
            report("PROTECTED_INACTIVE_TASK", (block.id, task.id))
        reserved[task.id] += block.end_slot - block.start_slot
        if any(
            block.start_slot < end and start < block.end_slot
            for start, end in snapshot.busy_slot_ranges
        ):
            report("PROTECTED_BUSY_CONFLICT", (block.id, task.id))
    for task_id, slots in reserved.items():
        if slots > tasks[task_id].required_slots:
            report(
                "LOCK_EXCEEDS_REMAINING",
                (task_id,),
                reserved_slots=slots,
                required_slots=tasks[task_id].required_slots,
            )
    return violations


def apply_work_observation(
    task: TaskSpec,
    observed_minutes: int,
    new_remaining_minutes: int | None = None,
    complete: bool = False,
) -> TaskSpec:
    """Derive a new task; persisting an append-only observation is a command concern."""
    if (
        isinstance(observed_minutes, bool)
        or not isinstance(observed_minutes, int)
        or observed_minutes < 0
    ):
        raise ValueError("observed_minutes must be a nonnegative integer")
    if new_remaining_minutes is None and not complete:
        raise ValueError("REMAINING_ESTIMATE_REQUIRED")
    if complete and new_remaining_minutes not in (None, 0):
        raise ValueError("completion conflicts with a nonzero remaining estimate")
    data = task.model_dump(exclude={"required_slots"})
    data["remaining_minutes"] = 0 if complete else new_remaining_minutes
    if complete:
        data["state"] = TaskState.DONE
    return TaskSpec(**data)
