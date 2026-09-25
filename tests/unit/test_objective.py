import pytest

from tests.unit.test_validator import block, candidate, snapshot, task


def test_all_five_objective_components_have_hand_computed_denominators():
    from planner.solver.objective import score_candidate

    a = task(slots=4)
    s = snapshot([a], preferred_windows=((0, 1),))
    old = candidate(s, [block(a, 0, 4)])
    s = s.model_copy(update={"prior_candidate": old})
    c = candidate(s, [block(a, 0, 1), block(a, 2, 3)])
    score = score_candidate(s, c)
    assert score.future_work_deficit == 0.5
    assert score.disruption == 0.5
    assert score.preference_mismatch == 0.5
    assert score.fragmentation == 1
    assert score.completion_delay == 0.375
    assert score.total_penalty == 56.25
    assert score.quality == 0.4375


def test_empty_denominators_are_zero():
    from planner.solver.objective import score_candidate

    s = snapshot([task(slots=0)])
    score = score_candidate(s, candidate(s, []))
    assert score.total_penalty == 0
    assert score.quality == 1


def test_unknown_objective_version_is_rejected():
    from planner.solver.objective import score_candidate

    s = snapshot(objective_version="future")
    with pytest.raises(ValueError, match="OBJECTIVE_VERSION"):
        score_candidate(s, candidate(s, []))
