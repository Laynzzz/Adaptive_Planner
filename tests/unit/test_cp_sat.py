import pytest
from ortools.sat.python import cp_model

from planner.domain.contracts import Dependency
from tests.unit.test_validator import OWNER, block, snapshot, task


def counterexample():
    from pathlib import Path

    from planner.domain.contracts import InputSnapshot

    return InputSnapshot.model_validate_json(
        (Path(__file__).parents[1] / "fixtures/solver/greedy_fails_but_feasible.json").read_text()
    )


def test_cp_recovers_a_hand_proven_greedy_failure():
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.greedy import greedy_schedule
    from planner.solver.validator import validate_candidate

    s = counterexample()
    assert greedy_schedule(s).status == "UNKNOWN"
    result = solve_cp_sat(s, budget_ms=2000, seed=7)
    assert result.status == "OPTIMAL"
    assert validate_candidate(s, result) == []
    assert [(b.task_id, b.start_slot, b.end_slot) for b in result.blocks] == [
        (s.tasks[1].id, 0, 3),
        (s.tasks[0].id, 3, 5),
    ]


def test_capacity_is_proven_infeasible():
    from planner.solver.cp_sat import solve_cp_sat

    s = snapshot([task(1, 4, deadline_slot=4), task(2, 4, deadline_slot=4)])
    assert solve_cp_sat(s, 2000, 7).status == "INFEASIBLE"


def test_solver_optimum_matches_exhaustive_tiny_reference():
    from benchmarks.tiny_reference import enumerate_candidates
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.objective import integer_penalty

    scenarios = [counterexample(), snapshot([task(slots=3)], preferred_windows=((3, 5),))]
    for s in scenarios:
        candidates = list(enumerate_candidates(s))
        assert candidates
        result = solve_cp_sat(s, 2000, 7)
        assert result.status == "OPTIMAL"
        assert integer_penalty(result.score) == min(integer_penalty(c.score) for c in candidates)


def test_unknown_timeout_keeps_validated_fallback_distinct_from_unresolved(monkeypatch):
    import planner.solver.cp_sat as module

    monkeypatch.setattr(module, "_run", lambda *args: (cp_model.CpSolver(), cp_model.UNKNOWN))
    result = module.solve_cp_sat(snapshot(), 2000, 7)
    assert result.status == "FEASIBLE"
    assert result.source_policy == "GREEDY_FALLBACK"
    assert result.solver_metadata.reason_code == "CP_UNKNOWN"
    unresolved = module.solve_cp_sat(counterexample(), 2000, 7)
    assert unresolved.status == "UNKNOWN"
    assert unresolved.blocks == ()


def test_model_invalid_status_is_not_infeasible(monkeypatch):
    import planner.solver.cp_sat as module

    monkeypatch.setattr(module, "_run", lambda *args: (cp_model.CpSolver(), cp_model.MODEL_INVALID))
    assert module.solve_cp_sat(counterexample(), 2000, 7).status == "MODEL_INVALID"


def test_protected_blocks_remain_exact_and_optional_predecessor_blocks_successor():
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.validator import validate_candidate

    a, b = task(1, 9), task(2, 1)
    protected = block(a, 2, 4, locked=True)
    s = snapshot(
        [a, b],
        protected_blocks=(protected,),
        dependencies=(Dependency(owner_id=OWNER, predecessor_id=a.id, successor_id=b.id),),
    )
    c = solve_cp_sat(s, 2000, 7)
    assert c.status in ("FEASIBLE", "OPTIMAL")
    assert protected in c.blocks
    assert all(x.task_id != b.id for x in c.blocks)
    assert not validate_candidate(s, c)


@pytest.mark.parametrize("short", [True, False])
def test_split_remainder_matches_validator(short):
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.validator import validate_candidate

    a = task(slots=3, deadline_slot=8).model_copy(
        update={"min_block_slots": 2, "max_block_slots": 2, "short_final_allowed": short}
    )
    s = snapshot([a])
    c = solve_cp_sat(s, 2000, 7)
    if short:
        assert c.status == "OPTIMAL"
        assert not validate_candidate(s, c)
    else:
        assert c.status == "INFEASIBLE"


def test_objective_with_prior_and_preferences_matches_exhaustive_optimum():
    from benchmarks.tiny_reference import enumerate_candidates
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.objective import integer_penalty
    from tests.unit.test_validator import candidate

    a = task(slots=3)
    s = snapshot([a], availability=((0, 5),), horizon_end_slot=5, preferred_windows=((3, 5),))
    s = s.model_copy(update={"prior_candidate": candidate(s, [block(a, 0, 3)])})
    c = solve_cp_sat(s, 2000, 7)
    assert c.status == "OPTIMAL"
    assert integer_penalty(c.score) == min(
        integer_penalty(x.score) for x in enumerate_candidates(s)
    )


def test_no_undocumented_maximum_number_of_blocks():
    from planner.solver.cp_sat import solve_cp_sat

    a = task(slots=13, deadline_slot=30).model_copy(update={"max_block_slots": 1})
    s = snapshot(
        [a], availability=tuple((2 * i, 2 * i + 1) for i in range(13)), horizon_end_slot=30
    )
    c = solve_cp_sat(s, 2000, 7)
    assert c.status in ("OPTIMAL", "FEASIBLE")
    assert len(c.blocks) == 13


def test_in_progress_short_reservation_is_counted_without_moving():
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.validator import validate_candidate

    a = task(slots=3, deadline_slot=8).model_copy(update={"min_block_slots": 2})
    protected = block(a, 0, 1, source="IN_PROGRESS", locked=True)
    s = snapshot([a], protected_blocks=(protected,))
    c = solve_cp_sat(s, 2000, 7)
    assert protected in c.blocks
    assert not validate_candidate(s, c)


def test_busy_conflict_with_lock_is_input_conflict_not_silently_removed():
    from planner.solver.cp_sat import solve_cp_sat

    a = task()
    protected = block(a, 0, 2, locked=True)
    s = snapshot([a], protected_blocks=(protected,), busy_slot_ranges=((1, 2),))
    c = solve_cp_sat(s, 2000, 7)
    assert c.status == "MODEL_INVALID"
    assert "PROTECTED_BUSY_CONFLICT" in {v.code for v in c.constraint_report}


def test_excessive_model_resources_are_rejected_explicitly_not_truncated():
    from planner.solver.cp_sat import solve_cp_sat

    tasks = [task(i + 1, 1000) for i in range(30)]
    s = snapshot(tasks, availability=((0, 1000),), horizon_end_slot=1000)
    c = solve_cp_sat(s, 2000, 7)
    assert c.status == "MODEL_INVALID"
    assert c.constraint_report[0].code == "MODEL_RESOURCE_LIMIT"
    assert c.constraint_report[0].facts["resource"] == "optional_intervals"


@pytest.mark.parametrize("required", [True, False])
def test_unsplittable_work_below_minimum_is_not_allocated_without_short_final(required):
    from planner.solver.cp_sat import solve_cp_sat
    from planner.solver.validator import validate_candidate

    small = task(1, 1, deadline_slot=4 if required else None).model_copy(
        update={
            "splittable": False,
            "min_block_slots": 2,
            "max_block_slots": 2,
            "short_final_allowed": False,
        }
    )
    other = task(2, 2, deadline_slot=4)
    s = snapshot([small, other], availability=((0, 4),), horizon_end_slot=4)
    c = solve_cp_sat(s, 2000, 7)
    if required:
        assert c.status == "INFEASIBLE"
    else:
        assert c.status == "OPTIMAL"
        assert c.source_policy == "CP_SAT"
        assert {b.task_id for b in c.blocks} == {other.id}
        assert validate_candidate(s, c) == []


def test_cp_disruption_uses_prior_utc_instants_across_midnight():
    from planner.solver.cp_sat import solve_cp_sat
    from tests.unit.test_objective import next_day_replan

    s = next_day_replan()
    c = solve_cp_sat(s, 2000, 7)
    assert c.status == "OPTIMAL"
    assert [(b.start_slot, b.end_slot) for b in c.blocks] == [(4, 6)]
    assert c.score.disruption == 0


def test_cold_cp_does_not_compute_greedy_or_return_fallback(monkeypatch):
    import planner.solver.cp_sat as module

    def unexpected(_):
        raise AssertionError("Cold CP must not run greedy.")

    monkeypatch.setattr(module, "greedy_schedule", unexpected)
    result = module.solve_cp_sat(
        snapshot(), budget_ms=0, use_greedy_hint=False, allow_greedy_fallback=False
    )
    assert result.status == "UNKNOWN"
    assert result.source_policy == "CP_SAT"


def test_precomputed_warm_candidate_is_validated_without_recomputing(monkeypatch):
    import planner.solver.cp_sat as module
    from planner.solver.greedy import greedy_schedule

    s = snapshot()
    warm = greedy_schedule(s)

    def unexpected(_):
        raise AssertionError("Precomputed warm candidate must not rerun greedy.")

    monkeypatch.setattr(module, "greedy_schedule", unexpected)
    result = module.solve_cp_sat(s, budget_ms=0, warm_candidate=warm)
    assert result.status == "FEASIBLE"
    assert result.blocks == warm.blocks
    invalid = warm.model_copy(update={"snapshot_hash": "wrong-snapshot"})
    result = module.solve_cp_sat(s, budget_ms=0, warm_candidate=invalid)
    assert result.status == "UNKNOWN"
