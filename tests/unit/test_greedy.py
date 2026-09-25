from planner.domain.contracts import Dependency
from tests.unit.test_validator import OWNER, block, snapshot, task


def test_greedy_is_deterministic_and_honors_priority_and_topology():
    from planner.solver.greedy import greedy_schedule
    from planner.solver.validator import validate_candidate

    a, b = task(1, priority=1), task(2, priority=5)
    s = snapshot(
        [a, b], dependencies=(Dependency(owner_id=OWNER, predecessor_id=a.id, successor_id=b.id),)
    )
    first = greedy_schedule(s)
    assert first == greedy_schedule(s)
    assert first.blocks[0].task_id == a.id
    assert validate_candidate(s, first) == []


def test_greedy_preserves_protected_blocks_and_schedules_remaining_work():
    from planner.solver.greedy import greedy_schedule
    from planner.solver.validator import validate_candidate

    a = task(slots=4)
    fixed = block(a, 4, 6, locked=True)
    s = snapshot([a], protected_blocks=(fixed,))
    result = greedy_schedule(s)
    assert fixed in result.blocks
    assert sum(b.end_slot - b.start_slot for b in result.blocks) == 4
    assert validate_candidate(s, result) == []


def test_failed_greedy_is_unknown_not_infeasible():
    from planner.solver.greedy import greedy_schedule

    a, b = task(1, 4, deadline_slot=4), task(2, 4, deadline_slot=4)
    assert greedy_schedule(snapshot([a, b])).status == "UNKNOWN"


def test_short_final_remainder_and_optional_partial_work():
    from planner.solver.greedy import greedy_schedule
    from planner.solver.validator import validate_candidate

    a = task(slots=5).model_copy(update={"min_block_slots": 2, "short_final_allowed": True})
    s = snapshot([a], availability=((0, 2), (4, 7)))
    result = greedy_schedule(s)
    assert result.status == "FEASIBLE"
    assert validate_candidate(s, result) == []
    assert sum(b.end_slot - b.start_slot for b in result.blocks) == 5
