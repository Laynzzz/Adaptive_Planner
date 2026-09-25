from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.test_validator import OWNER, block, codes, snapshot, task


@settings(max_examples=1000, deadline=None, derandomize=True)
@given(st.integers(1, 6), st.integers(0, 31), st.integers(1, 5), st.booleans())
def test_thousand_generated_invariants(work, offset, priority, split):
    from planner.solver.greedy import greedy_schedule
    from planner.solver.validator import validate_candidate

    a, b = task(1, work, priority=priority, splittable=split), task(2, work)
    s = snapshot([a, b], availability=((offset, offset + 12),), horizon_end_slot=offset + 12)
    c = greedy_schedule(s)
    if c.status == "FEASIBLE":
        assert validate_candidate(s, c) == []
    bad = [block(a, offset, offset + 1), block(b, offset, offset + 1)]
    assert "OVERLAP" in codes(s, bad)
    bad[0] = bad[0].model_copy(update={"owner_id": OWNER.__class__(int=999)})
    assert "BLOCK_OWNER_MISMATCH" in codes(s, bad)


@settings(max_examples=100, deadline=None, derandomize=True)
@given(st.integers(1, 4), st.integers(1, 4), st.booleans(), st.integers(0, 3))
def test_cp_small_generated_schedules_match_independent_oracle(first, second, split, gap):
    from benchmarks.tiny_reference import enumerate_candidates
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.objective import integer_penalty
    from planner.solver.validator import validate_candidate

    a = task(1, first, deadline_slot=5, splittable=split)
    b = task(2, second, deadline_slot=5, release_slot=gap, splittable=split)
    s = snapshot([a, b], availability=((0, 5),), horizon_end_slot=5)
    candidates = list(enumerate_candidates(s))
    c = solve_cp_sat(s, 2000, 7)
    if candidates:
        assert c.status == "OPTIMAL"
        assert validate_candidate(s, c) == []
        assert integer_penalty(c.score) == min(integer_penalty(x.score) for x in candidates)
    else:
        assert c.status == "INFEASIBLE"
