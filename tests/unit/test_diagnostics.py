from tests.unit.test_cp_sat import counterexample
from tests.unit.test_validator import snapshot, task


def test_capacity_diagnostic_reports_numbers_not_minimal_conflict_claim():
    from planner.solver.diagnostics import diagnose

    s = snapshot([task(1, 4, deadline_slot=4), task(2, 4, deadline_slot=4)])
    reports = diagnose(s)
    capacity = next(v for v in reports if v.code == "CAPACITY_BEFORE_DEADLINE")
    assert capacity.facts["required_slots"] == 8
    assert capacity.facts["available_slots"] == 4


def test_greedy_failure_is_not_a_proof_of_infeasibility():
    from planner.solver.diagnostics import diagnose

    assert diagnose(counterexample()) == []


def test_unsplittable_window_and_input_error_are_distinct():
    from planner.solver.diagnostics import diagnose

    a = task(slots=3, deadline_slot=8, splittable=False)
    s = snapshot([a], availability=((0, 2), (4, 6)))
    assert "NO_CONTIGUOUS_WINDOW" in {v.code for v in diagnose(s)}
