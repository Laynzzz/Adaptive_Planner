from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from planner.domain.contracts import Block, FeatureVector, Score, TaskSpec, Violation

OWNER = UUID("00000000-0000-0000-0000-000000000001")
TASK = UUID("00000000-0000-0000-0000-000000000002")


def test_remaining_estimate_is_preserved_while_slots_are_derived():
    task = TaskSpec(id=TASK, owner_id=OWNER, title="Draft", remaining_minutes=31)
    assert task.required_slots == 3
    assert task.model_dump()["required_slots"] == 3
    with pytest.raises(ValidationError):
        task.remaining_minutes = 15
    with pytest.raises(ValidationError):
        TaskSpec(id=TASK, owner_id=OWNER, title="Draft", remaining_minutes=31, required_slots=1)


@pytest.mark.parametrize("values", [(float("nan"),), (float("inf"),)])
def test_feature_vector_rejects_nonfinite_values(values):
    with pytest.raises(ValidationError):
        FeatureVector(version="v1", names=("task_count",), values=values)


def test_feature_vector_rejects_mismatched_or_duplicate_ordered_names():
    with pytest.raises(ValidationError):
        FeatureVector(version="v1", names=("a", "b"), values=(1.0,))
    with pytest.raises(ValidationError):
        FeatureVector(version="v1", names=("a", "a"), values=(1.0, 2.0))


def test_score_bounds_and_weighted_quality_are_enforced():
    score = Score(
        future_work_deficit=1,
        disruption=0,
        preference_mismatch=0,
        fragmentation=0,
        completion_delay=0,
    )
    assert score.total_penalty == 30
    assert score.quality == 0.7
    with pytest.raises(ValidationError):
        Score(future_work_deficit=1.01)


def test_block_normalizes_utc_and_rejects_naive_or_empty_instants():
    block = Block(
        id=TASK,
        owner_id=OWNER,
        task_id=TASK,
        start=datetime.fromisoformat("2026-09-25T09:00:00-04:00"),
        end=datetime.fromisoformat("2026-09-25T09:30:00-04:00"),
        start_slot=52,
        end_slot=54,
    )
    assert block.start == datetime(2026, 9, 25, 13, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Block(
            id=TASK,
            owner_id=OWNER,
            task_id=TASK,
            start=datetime(2026, 9, 25, 13),
            end=datetime(2026, 9, 25, 14),
            start_slot=52,
            end_slot=56,
        )


def test_violation_facts_cannot_be_mutated_after_snapshot_creation():
    item = Violation(code="LOCK_EXCEEDS_REMAINING", facts={"reserved_slots": 3})
    assert item.facts["reserved_slots"] == 3
    with pytest.raises(TypeError):
        item.facts["reserved_slots"] = 1
    assert "reserved_slots" in item.model_dump_json()


def test_empty_fact_mapping_is_also_immutable():
    item = Violation(code="DEPENDENCY_CYCLE")
    with pytest.raises(TypeError):
        item.facts["injected"] = True


def test_task_bounds_and_negative_work_are_rejected():
    for changes in (
        {"remaining_minutes": -1},
        {"priority": 6},
        {"min_block_slots": 5, "max_block_slots": 2},
    ):
        data = {"id": TASK, "owner_id": OWNER, "title": "Draft", "remaining_minutes": 30}
        data.update(changes)
        with pytest.raises(ValidationError):
            TaskSpec(**data)


def test_shared_snapshot_builder_has_due_today_tasks_and_preserves_bad_overrides():
    from tests.fixtures.builders import block, snapshot

    s = snapshot()
    assert [t.deadline_slot for t in s.tasks] == [68, 68]
    assert [t.required_slots for t in s.tasks] == [4, 4]
    forged = block(s.tasks[0], 36, 40, owner_id=TASK)
    assert forged.owner_id == TASK


def test_committed_fixture_loader_uses_production_normalization():
    from tests.fixtures import builders

    assert hasattr(builders, "load_fixture")
    s = builders.load_fixture("time/busy_0907_0922.json")
    assert s.busy_slot_ranges == ((36, 38),)
    assert s.tasks[0].required_slots == 3
