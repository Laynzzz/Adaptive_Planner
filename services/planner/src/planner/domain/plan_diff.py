"""Structured plan changes without invented causal narratives."""

from planner.domain.contracts import BlockMove, Candidate, PlanDiff


def diff_plans(old: Candidate, new: Candidate) -> PlanDiff:
    previous = {block.id: block for block in old.blocks}
    current = {block.id: block for block in new.blocks}
    retained = []
    moved = []
    for block in new.blocks:
        before = previous.get(block.id)
        if before is None:
            continue
        if (before.task_id, before.start, before.end) == (block.task_id, block.start, block.end):
            retained.append(block)
        else:
            moved.append(BlockMove(old=before, new=block, reason_codes=("BLOCK_TIME_CHANGED",)))
    added = tuple(block for block in new.blocks if block.id not in previous)
    removed = tuple(block for block in old.blocks if block.id not in current)
    reasons = tuple(
        code
        for enabled, code in (
            (bool(moved), "BLOCK_TIME_CHANGED"),
            (bool(added), "BLOCK_ADDED"),
            (bool(removed), "BLOCK_REMOVED"),
        )
        if enabled
    )
    return PlanDiff(
        retained=tuple(retained),
        moved=tuple(moved),
        added=added,
        removed=removed,
        reason_codes=reasons,
    )
