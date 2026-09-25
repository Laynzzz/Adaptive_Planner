"""Hand-specified synthetic fixtures; overrides never repair inconsistent test inputs.

The default clock is 2026-09-25 09:00 UTC and slot zero is that day's UTC
midnight. Blocks derive timestamps only when the caller does not provide them;
explicit timestamps, owners, revisions and hashes remain exactly as supplied.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid5

from planner.domain.contracts import Block, Candidate, Deadline, InputSnapshot, TaskSpec
from planner.domain.time_rules import normalize_time_inputs

OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
TASK_ID = UUID("00000000-0000-0000-0000-000000000002")
SECOND_TASK_ID = UUID("00000000-0000-0000-0000-000000000003")
NOW = datetime(2026, 9, 25, 9, tzinfo=UTC)
SLOT_ORIGIN = datetime(2026, 9, 25, tzinfo=UTC)


def task(**changes) -> TaskSpec:
    values = dict(
        id=TASK_ID,
        owner_id=OWNER_ID,
        title="Write synthetic draft",
        remaining_minutes=60,
        release_slot=36,
        deadline=Deadline(kind="TIMESTAMP", value="2026-09-25T17:00:00Z"),
        deadline_at=datetime(2026, 9, 25, 17, tzinfo=UTC),
        deadline_slot=68,
    )
    values.update(changes)
    return TaskSpec(**values)


def snapshot(**changes) -> InputSnapshot:
    base = normalize_time_inputs(
        {
            "owner_id": str(OWNER_ID),
            "timezone": "UTC",
            "planning_revision": 1,
            "tasks": [
                {
                    "id": str(TASK_ID),
                    "title": "Write synthetic draft",
                    "remaining_minutes": 60,
                    "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T17:00:00Z"},
                },
                {
                    "id": str(SECOND_TASK_ID),
                    "title": "Review synthetic draft",
                    "remaining_minutes": 60,
                    "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T17:00:00Z"},
                },
            ],
            "availability": [{"start": "2026-09-25T09:00:00Z", "end": "2026-09-25T17:00:00Z"}],
        },
        NOW,
    )
    values = base.model_dump(exclude_computed_fields=True)
    values.update(changes)
    return InputSnapshot(**values)


def block(
    task_spec: TaskSpec, start: int, end: int, *, slot_origin: datetime = SLOT_ORIGIN, **changes
) -> Block:
    values = dict(
        id=uuid5(task_spec.id, f"{start}:{end}"),
        owner_id=task_spec.owner_id,
        task_id=task_spec.id,
        start_slot=start,
        end_slot=end,
        start=slot_origin + timedelta(minutes=15 * start),
        end=slot_origin + timedelta(minutes=15 * end),
        source="FIXTURE",
    )
    values.update(changes)
    return Block(**values)


def candidate(blocks=(), *, snapshot_spec: InputSnapshot | None = None, **changes) -> Candidate:
    source = snapshot_spec if snapshot_spec is not None else snapshot()
    values = dict(
        snapshot_hash=source.snapshot_hash,
        planning_revision=source.planning_revision,
        status="FEASIBLE",
        source_policy="FIXTURE",
        blocks=tuple(blocks),
    )
    values.update(changes)
    return Candidate(**values)


def load_fixture(name: str) -> InputSnapshot:
    """Load committed raw inputs with their explicit clock via the production parser."""
    fixture = json.loads((Path(__file__).parent / name).read_text(encoding="utf-8"))
    return normalize_time_inputs(fixture["raw"], datetime.fromisoformat(fixture["now"]))


def valid_task_command(**changes) -> dict:
    """A fixed-clock command; the API wrapper moves its key into the required header."""
    from uuid import uuid4

    values = {
        "title": "Synthetic 60-minute task",
        "remaining_minutes": 60,
        "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T17:00:00Z", "timezone": "UTC"},
        "expected_revision": 0,
        "idempotency_key": str(uuid4()),
    }
    values.update(changes)
    return values
