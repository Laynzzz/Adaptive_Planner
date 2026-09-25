from datetime import timedelta
from uuid import uuid4

from planner.domain.plan_diff import diff_plans
from planner.solver.block_matching import match_blocks
from tests.fixtures.builders import block, candidate, snapshot


def test_moved_work_keeps_stable_id_and_reports_original_and_new_time():
    s = snapshot()
    before = block(s.tasks[0], 36, 40)
    proposed = block(s.tasks[0], 38, 42, id=uuid4())
    old = candidate([before], snapshot_spec=s)
    matched = match_blocks(old, candidate([proposed], snapshot_spec=s))
    assert matched.blocks[0].id == before.id
    changes = diff_plans(old, matched)
    assert len(changes.moved) == 1
    assert changes.moved[0].old.start_slot == 36
    assert changes.moved[0].new.start_slot == 38
    assert not changes.added and not changes.removed


def test_matching_prefers_greatest_overlap_and_does_not_reuse_old_ids():
    s = snapshot()
    old = candidate([block(s.tasks[0], 36, 40), block(s.tasks[0], 44, 48)], snapshot_spec=s)
    new = candidate(
        [
            block(s.tasks[0], 37, 41, id=uuid4()),
            block(s.tasks[0], 45, 49, id=uuid4()),
            block(s.tasks[0], 52, 54, id=uuid4()),
        ],
        snapshot_spec=s,
    )
    matched = match_blocks(old, new)
    assert matched.blocks[0].id == old.blocks[0].id
    assert matched.blocks[1].id == old.blocks[1].id
    assert len({b.id for b in matched.blocks}) == 3
    diff = diff_plans(old, matched)
    assert len(diff.added) == 1
    assert len(diff.moved) == 2


def test_locked_id_is_reserved_and_missing_lock_is_not_silently_repaired():
    s = snapshot()
    locked = block(s.tasks[0], 36, 40, locked=True)
    old = candidate([locked], snapshot_spec=s)
    forged = block(s.tasks[0], 37, 41, id=uuid4())
    new = match_blocks(old, candidate([forged], snapshot_spec=s))
    assert new.blocks[0].id == forged.id
    assert diff_plans(old, new).removed == (locked,)


def test_identical_utc_interval_is_retained_across_snapshot_slot_origins():
    s = snapshot()
    before = block(s.tasks[0], 132, 136)
    new = block(s.tasks[0], 36, 40, slot_origin=s.slot_origin + timedelta(days=1), id=uuid4())
    old = candidate([before], snapshot_spec=s)
    after = match_blocks(old, candidate([new], snapshot_spec=s))
    changes = diff_plans(old, after)
    assert changes.retained == (after.blocks[0],)
    assert changes.moved == ()


def test_newly_protected_id_cannot_be_reassigned_by_overlap_matching():
    s = snapshot()
    old = candidate([block(s.tasks[0], 36, 40), block(s.tasks[0], 44, 48)], snapshot_spec=s)
    protected = old.blocks[1].model_copy(
        update={
            "start": old.blocks[0].start,
            "end": old.blocks[0].end,
            "start_slot": 36,
            "end_slot": 40,
            "locked": True,
        }
    )
    matched = match_blocks(old, candidate([protected], snapshot_spec=s))
    assert matched.blocks[0].id == protected.id

def test_unmatched_new_block_cannot_duplicate_a_reassigned_old_id():
    s = snapshot()
    before = block(s.tasks[0], 36, 40)
    old = candidate([before], snapshot_spec=s)
    overlapping = block(s.tasks[0], 36, 40, id=uuid4())
    added = block(s.tasks[0], 48, 52, id=before.id)
    matched = match_blocks(old, candidate([overlapping, added], snapshot_spec=s))
    assert len({b.id for b in matched.blocks}) == 2
    assert matched.blocks[0].id == before.id
