from datetime import UTC, datetime

import pytest

from planner.domain.task_rules import apply_work_observation, validate_tasks
from planner.domain.time_rules import normalize_time_inputs
from tests.unit.test_time_rules import TASK, raw

NOW = datetime(2026, 9, 25, 9, tzinfo=UTC)
OTHER = "00000000-0000-0000-0000-000000000003"


def codes(data):
    return {v.code for v in validate_tasks(normalize_time_inputs(data, NOW))}


def test_cycle_and_cross_owner_dependencies_rejected():
    tasks = [
        {"id": TASK, "title": "One", "remaining_minutes": 30},
        {"id": OTHER, "title": "Two", "remaining_minutes": 30},
    ]
    edges = [
        {"predecessor_id": TASK, "successor_id": OTHER},
        {"predecessor_id": OTHER, "successor_id": TASK},
    ]
    assert "DEPENDENCY_CYCLE" in codes(raw(tasks=tasks, dependencies=edges))
    tasks[1]["owner_id"] = OTHER
    assert "CROSS_OWNER_DEPENDENCY" in codes(raw(tasks=tasks, dependencies=edges))


def test_cancelled_predecessor_unresolved_and_done_predecessor_satisfied():
    tasks = [
        {"id": TASK, "title": "One", "remaining_minutes": 0, "state": "CANCELLED"},
        {"id": OTHER, "title": "Two", "remaining_minutes": 30},
    ]
    edges = [{"predecessor_id": TASK, "successor_id": OTHER}]
    assert "CANCELLED_PREDECESSOR" in codes(raw(tasks=tasks, dependencies=edges))
    tasks[0]["state"] = "DONE"
    assert codes(raw(tasks=tasks, dependencies=edges)) == set()


def test_missing_dependency_and_past_deadline_remain_unresolved():
    assert "DEPENDENCY_TASK_MISSING" in codes(
        raw(dependencies=[{"predecessor_id": OTHER, "successor_id": TASK}])
    )
    assert "PAST_DEADLINE" in codes(
        raw(
            tasks=[
                {
                    "id": TASK,
                    "title": "One",
                    "remaining_minutes": 30,
                    "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T08:59Z"},
                }
            ]
        )
    )


def test_locked_excess_and_new_fixed_event_conflict_are_explicit():
    protected = [
        {
            "id": OTHER,
            "task_id": TASK,
            "start": "2026-09-25T09:00Z",
            "end": "2026-09-25T10:00Z",
            "locked": True,
        }
    ]
    found = codes(
        raw(
            protected_blocks=protected,
            fixed_events=[{"start": "2026-09-25T09:30Z", "end": "2026-09-25T09:45Z"}],
        )
    )
    assert {"LOCK_EXCEEDS_REMAINING", "PROTECTED_BUSY_CONFLICT"} <= found


def test_in_progress_future_only_counts_and_completed_history_is_excluded():
    data = raw(
        tasks=[{"id": TASK, "title": "One", "remaining_minutes": 30, "state": "IN_PROGRESS"}],
        protected_blocks=[
            {
                "id": OTHER,
                "task_id": TASK,
                "start": "2026-09-25T08:30Z",
                "end": "2026-09-25T09:30Z",
                "source": "IN_PROGRESS",
            }
        ],
    )
    s = normalize_time_inputs(data, NOW)
    assert s.protected_blocks[0].start_slot == 36
    assert s.protected_blocks[0].end_slot == 38
    assert validate_tasks(s) == []
    data["protected_blocks"][0]["source"] = "COMPLETED"
    assert normalize_time_inputs(data, NOW).protected_blocks == ()


def test_partial_observed_work_requires_new_estimate_or_explicit_completion():
    task = normalize_time_inputs(raw(), NOW).tasks[0]
    with pytest.raises(ValueError, match="REMAINING_ESTIMATE_REQUIRED"):
        apply_work_observation(task, observed_minutes=15)
    updated = apply_work_observation(task, observed_minutes=15, new_remaining_minutes=20)
    assert updated.remaining_minutes == 20
    assert updated.required_slots == 2
    assert updated.state == "TODO"
    done = apply_work_observation(task, observed_minutes=15, complete=True)
    assert done.state == "DONE"
    assert done.remaining_minutes == 0
    assert task.remaining_minutes == 31
