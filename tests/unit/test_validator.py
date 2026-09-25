from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from planner.domain.contracts import Block, Candidate, Dependency, InputSnapshot, TaskSpec

ORIGIN = datetime(2026, 9, 25, tzinfo=UTC)
OWNER = UUID(int=1)


def task(number=1, slots=2, **changes):
    return TaskSpec(
        id=UUID(int=100 + number),
        owner_id=OWNER,
        title=f"Task {number}",
        remaining_minutes=15 * slots,
        min_block_slots=1,
        max_block_slots=4,
        **changes,
    )


def snapshot(tasks=None, **changes):
    values = dict(
        id=UUID(int=2),
        snapshot_hash="fixture",
        owner_id=OWNER,
        planning_revision=1,
        reference_now=ORIGIN,
        timezone="UTC",
        slot_origin=ORIGIN,
        horizon_start=ORIGIN,
        horizon_end=ORIGIN + timedelta(hours=2),
        horizon_start_slot=0,
        horizon_end_slot=8,
        availability=((0, 8),),
        tasks=tuple(tasks or [task()]),
    )
    values.update(changes)
    return InputSnapshot(**values)


def block(t, start, end, **changes):
    values = dict(
        id=UUID(int=1000 + t.id.int * 100 + start),
        owner_id=t.owner_id,
        task_id=t.id,
        start=ORIGIN + timedelta(minutes=15 * start),
        end=ORIGIN + timedelta(minutes=15 * end),
        start_slot=start,
        end_slot=end,
    )
    values.update(changes)
    return Block(**values)


def candidate(s, blocks):
    return Candidate(
        snapshot_hash=s.snapshot_hash,
        planning_revision=s.planning_revision,
        status="FEASIBLE",
        source_policy="TEST",
        blocks=tuple(blocks),
    )


def codes(s, blocks):
    from planner.solver.validator import validate_candidate

    return {v.code for v in validate_candidate(s, candidate(s, blocks))}


def test_adjacent_blocks_are_valid_but_overlap_is_rejected():
    a, b = task(1), task(2)
    s = snapshot([a, b])
    assert codes(s, [block(a, 0, 2), block(b, 2, 4)]) == set()
    assert "OVERLAP" in codes(s, [block(a, 0, 2), block(b, 1, 3)])


def test_forged_owner_is_rejected():
    s = snapshot()
    assert "BLOCK_OWNER_MISMATCH" in codes(s, [block(s.tasks[0], 0, 2, owner_id=UUID(int=9))])


@pytest.mark.parametrize(
    ("changes", "interval", "code"),
    [
        ({"deadline_slot": 3}, (2, 4), "DEADLINE"),
        ({"release_slot": 2}, (0, 2), "RELEASE"),
        ({"deadline_slot": 8}, (0, 1), "WORKLOAD_DEFICIT"),
        ({}, (0, 3), "WORKLOAD_EXCESS"),
        ({"state": "DONE", "remaining_minutes": 0}, (0, 2), "INACTIVE_TASK"),
    ],
)
def test_task_constraints(changes, interval, code):
    a = task().model_copy(update=changes)
    assert code in codes(snapshot([a]), [block(a, *interval)])


def test_availability_busy_rounding_and_past_are_independent():
    s = snapshot(
        availability=((2, 8),),
        busy_slot_ranges=((3, 4),),
        reference_now=ORIGIN + timedelta(minutes=15),
    )
    a = s.tasks[0]
    assert "OUTSIDE_AVAILABILITY" in codes(s, [block(a, 0, 2)])
    assert "PAST_BLOCK" in codes(s, [block(a, 0, 2)])
    assert "BUSY_OVERLAP" in codes(s, [block(a, 2, 4)])
    malformed = block(a, 2, 4).model_copy(update={"end": ORIGIN + timedelta(minutes=61)})
    assert "SLOT_ROUNDING" in codes(s, [malformed])


def test_dependency_requires_complete_predecessor_before_any_successor():
    a, b = task(1, 4), task(2)
    s = snapshot(
        [a, b], dependencies=(Dependency(owner_id=OWNER, predecessor_id=a.id, successor_id=b.id),)
    )
    assert "DEPENDENCY" in codes(s, [block(a, 0, 2), block(b, 2, 4)])
    assert "DEPENDENCY" in codes(s, [block(a, 2, 6), block(b, 0, 2)])
    assert not codes(s, [block(a, 0, 4), block(b, 4, 6)])


def test_protected_identity_and_interval_are_exact():
    a = task()
    fixed = block(a, 2, 4, locked=True, source="IN_PROGRESS")
    s = snapshot([a], protected_blocks=(fixed,))
    assert not codes(s, [fixed])
    assert "PROTECTED_CHANGED" in codes(s, [block(a, 0, 2)])


def test_short_block_allowed_only_as_final_completed_remainder():
    a = task(slots=3).model_copy(update={"min_block_slots": 2, "short_final_allowed": True})
    s = snapshot([a])
    assert not codes(s, [block(a, 0, 2), block(a, 4, 5)])
    assert "BLOCK_LENGTH" in codes(s, [block(a, 0, 1), block(a, 2, 4)])
    assert "BLOCK_LENGTH" in codes(s, [block(a, 0, 1)])
