"""Deterministic block identities; UTC intervals are independent of snapshot grids."""

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from planner.domain.contracts import Candidate


def match_blocks(
    old: Candidate | None, new: Candidate, *, reference_now: datetime | None = None
) -> Candidate:
    if old is None:
        return new
    reserved = {block.id for block in old.blocks if block.locked} | {
        block.id for block in new.blocks if block.locked or block.source == "IN_PROGRESS"
    }
    used_old = set(reserved)
    assigned = {index: block.id for index, block in enumerate(new.blocks) if block.id in reserved}
    pairs = []
    for old_block in old.blocks:
        if old_block.id in used_old or (
            reference_now is not None and old_block.end <= reference_now
        ):
            continue
        for index, new_block in enumerate(new.blocks):
            if (
                index in assigned
                or old_block.task_id != new_block.task_id
                or old_block.owner_id != new_block.owner_id
            ):
                continue
            overlap = max(
                0,
                (
                    min(old_block.end, new_block.end) - max(old_block.start, new_block.start)
                ).total_seconds(),
            )
            pairs.append(
                (
                    -overlap,
                    new_block.start,
                    old_block.start,
                    str(old_block.id),
                    str(new_block.id),
                    index,
                    old_block.id,
                )
            )
    for *_, index, old_id in sorted(pairs):
        if index not in assigned and old_id not in used_old:
            assigned[index] = old_id
            used_old.add(old_id)
    claimed = set(assigned.values())
    occupied = claimed | {block.id for block in new.blocks}
    blocks = []
    for index, block in enumerate(new.blocks):
        identity = assigned.get(index, block.id)
        if index not in assigned and identity in claimed:
            counter = 0
            while identity in occupied:
                identity = uuid5(
                    NAMESPACE_URL,
                    f"planner-block:{block.id}:{block.start.isoformat()}:{index}:{counter}",
                )
                counter += 1
            occupied.add(identity)
        blocks.append(block.model_copy(update={"id": identity}))
    return new.model_copy(update={"blocks": tuple(blocks)})
