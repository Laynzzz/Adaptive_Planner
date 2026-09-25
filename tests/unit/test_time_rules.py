import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from planner.domain.time_rules import (
    normalize_time_inputs,
    preview_timezone_change,
    resolve_local_time,
)

OWNER = "00000000-0000-0000-0000-000000000001"
TASK = "00000000-0000-0000-0000-000000000002"


def raw(**changes):
    value = {
        "owner_id": OWNER,
        "timezone": "UTC",
        "planning_revision": 1,
        "availability": [{"start": "2026-09-25T09:00:00Z", "end": "2026-09-25T17:00:00Z"}],
        "tasks": [{"id": TASK, "title": "Write draft", "remaining_minutes": 31}],
    }
    value.update(changes)
    return value


def test_conservative_rounding_fixture():
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures/time/busy_0907_0922.json").read_text()
    )
    s = normalize_time_inputs(fixture["raw"], datetime.fromisoformat(fixture["now"]))
    assert s.busy_slot_ranges == ((36, 38),)
    assert s.tasks[0].required_slots == 3
    assert s.tasks[0].remaining_minutes == 31
    assert s.slot_origin == datetime(2026, 9, 25, tzinfo=UTC)


def test_now_release_deadline_and_availability_round_inward():
    s = normalize_time_inputs(
        raw(
            availability=[{"start": "2026-09-25T09:07Z", "end": "2026-09-25T11:22Z"}],
            tasks=[
                {
                    "id": TASK,
                    "title": "Review",
                    "remaining_minutes": 15,
                    "release_at": "2026-09-25T10:10Z",
                    "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T11:22Z"},
                }
            ],
        ),
        datetime(2026, 9, 25, 10, 10, tzinfo=UTC),
    )
    assert s.horizon_start_slot == 41
    assert s.availability == ((41, 45),)
    assert s.tasks[0].release_slot == 41
    assert s.tasks[0].deadline_slot == 45
    assert s.tasks[0].deadline.value == "2026-09-25T11:22Z"
    assert s.rounding_losses


def test_date_deadline_means_next_local_midnight():
    s = normalize_time_inputs(
        raw(
            timezone="America/New_York",
            tasks=[
                {
                    "id": TASK,
                    "title": "Draft",
                    "remaining_minutes": 15,
                    "deadline": {"kind": "DATE", "value": "2026-09-25"},
                }
            ],
        ),
        datetime(2026, 9, 25, tzinfo=UTC),
    )
    assert s.tasks[0].deadline_at == datetime(2026, 9, 26, 4, tzinfo=UTC)
    assert s.tasks[0].deadline.timezone == "America/New_York"


@pytest.mark.parametrize("local", [datetime(2026, 3, 8, 2, 30)])
def test_dst_gap_rejected(local):
    with pytest.raises(ValueError, match="NONEXISTENT_LOCAL_TIME"):
        resolve_local_time(local, "America/New_York")


def test_repeated_hour_requires_explicit_fold():
    local = datetime(2026, 11, 1, 1, 30)
    with pytest.raises(ValueError, match="AMBIGUOUS_LOCAL_TIME"):
        resolve_local_time(local, "America/New_York")
    assert resolve_local_time(local, "America/New_York", fold=0) == datetime(
        2026, 11, 1, 5, 30, tzinfo=UTC
    )
    assert resolve_local_time(local, "America/New_York", fold=1) == datetime(
        2026, 11, 1, 6, 30, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "now,end,slots",
    [
        (datetime(2026, 3, 1, 5, tzinfo=UTC), datetime(2026, 3, 15, 4, tzinfo=UTC), 1340),
        (datetime(2026, 10, 25, 4, tzinfo=UTC), datetime(2026, 11, 8, 5, tzinfo=UTC), 1348),
    ],
)
def test_horizon_enumerates_actual_dst_instants(now, end, slots):
    s = normalize_time_inputs(
        raw(
            timezone="America/New_York",
            availability=[{"start": now.isoformat(), "end": end.isoformat()}],
        ),
        now,
    )
    assert s.horizon_end == end
    assert s.horizon_end_slot - s.horizon_start_slot == slots


def test_timezone_preview_preserves_timestamp_and_reinterprets_date_without_mutation():
    data = raw(
        tasks=[
            {
                "id": TASK,
                "title": "Draft",
                "remaining_minutes": 30,
                "deadline": {"kind": "DATE", "value": "2026-09-25"},
            },
            {
                "id": "00000000-0000-0000-0000-000000000003",
                "title": "Call",
                "remaining_minutes": 30,
                "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T20:00:00Z"},
            },
        ],
        fixed_events=[{"start": "2026-09-25T12:00Z", "end": "2026-09-25T13:00Z"}],
    )
    preview = preview_timezone_change(data, "America/New_York", datetime(2026, 9, 25, tzinfo=UTC))
    assert data["timezone"] == "UTC"
    assert preview.tasks[0].deadline_at == datetime(2026, 9, 26, 4, tzinfo=UTC)
    assert preview.tasks[1].deadline_at == datetime(2026, 9, 25, 20, tzinfo=UTC)
    assert preview.busy_slot_ranges == ((48, 52),)


def test_hash_is_reproducible_and_revision_sensitive():
    now = datetime(2026, 9, 25, tzinfo=UTC)
    a = normalize_time_inputs(raw(), now)
    b = normalize_time_inputs(raw(), now)
    c = normalize_time_inputs(raw(planning_revision=2), now)
    assert a.snapshot_hash == b.snapshot_hash
    assert a.id == b.id
    assert a.snapshot_hash != c.snapshot_hash
    assert "31" in a.model_dump_json()


def test_naive_clock_and_caller_supplied_required_slots_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        normalize_time_inputs(raw(), datetime(2026, 9, 25))
    with pytest.raises(ValueError, match="required_slots"):
        normalize_time_inputs(
            raw(
                tasks=[{"id": TASK, "title": "Draft", "remaining_minutes": 31, "required_slots": 1}]
            ),
            datetime(2026, 9, 25, tzinfo=UTC),
        )


def test_original_local_availability_intent_is_visible():
    s = normalize_time_inputs(
        raw(
            timezone="America/New_York",
            availability=[{"start": "2026-09-25T09:07", "end": "2026-09-25T17:00"}],
        ),
        datetime(2026, 9, 25, tzinfo=UTC),
    )
    assert s.original_time_inputs[0].value == "2026-09-25T09:07"
    assert s.original_time_inputs[0].timezone == "America/New_York"
    assert s.availability == ((53, 84),)


def test_locked_block_is_not_silently_rounded_or_moved():
    with pytest.raises(ValueError, match="LOCK_NOT_GRID_ALIGNED"):
        normalize_time_inputs(
            raw(
                protected_blocks=[
                    {
                        "id": TASK,
                        "task_id": TASK,
                        "start": "2026-09-25T09:07Z",
                        "end": "2026-09-25T09:37Z",
                        "locked": True,
                    }
                ]
            ),
            datetime(2026, 9, 25, tzinfo=UTC),
        )


def test_in_progress_without_expected_end_is_rejected_explicitly():
    with pytest.raises(ValueError, match="EXPECTED_END_REQUIRED"):
        normalize_time_inputs(
            raw(
                protected_blocks=[
                    {
                        "id": TASK,
                        "task_id": TASK,
                        "start": "2026-09-25T09:00Z",
                        "source": "IN_PROGRESS",
                    }
                ]
            ),
            datetime(2026, 9, 25, tzinfo=UTC),
        )


def test_raw_forms_cannot_inject_solver_deadline_slots():
    with pytest.raises(ValueError, match="derived solver fields"):
        normalize_time_inputs(
            raw(
                tasks=[
                    {"id": TASK, "title": "Forged", "remaining_minutes": 30, "deadline_slot": 99999}
                ]
            ),
            datetime(2026, 9, 25, tzinfo=UTC),
        )
