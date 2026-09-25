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
