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


def next_day_replan():
    from datetime import timedelta

    from planner.domain.time_rules import normalize_time_inputs
    from tests.unit.test_validator import ORIGIN, OWNER

    a = task(slots=2)
    raw = {
        "owner_id": str(OWNER),
        "timezone": "UTC",
        "availability": [{"start": "2026-09-26T00:00:00Z", "end": "2026-09-26T02:00:00Z"}],
        "tasks": [
            {
                "id": str(a.id),
                "title": a.title,
                "remaining_minutes": 30,
                "min_block_slots": 1,
                "max_block_slots": 4,
                "deadline": {"kind": "TIMESTAMP", "value": "2026-09-26T02:00:00Z"},
            }
        ],
    }
    old = normalize_time_inputs(raw, ORIGIN)
    # Slot 100 on Sep25 means 01:00 Sep26; after midnight it is slot4.
    previous = candidate(old, [block(a, 100, 102)])
    return normalize_time_inputs({**raw, "prior_candidate": previous}, ORIGIN + timedelta(days=1))


def test_prior_reference_uses_absolute_instants_across_utc_midnight():
    from planner.solver.greedy import make_block
    from planner.solver.objective import score_candidate

    s = next_day_replan()
    unchanged = candidate(s, [make_block(s, s.tasks[0], 4, 6)])
    moved = candidate(s, [make_block(s, s.tasks[0], 0, 2)])
    assert score_candidate(s, unchanged).disruption == 0
    assert score_candidate(s, moved).disruption == 1
