"""Pure normalization using a fixed clock and actual UTC instants."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from planner.domain.contracts import (
    Block,
    Deadline,
    Dependency,
    InputSnapshot,
    OriginalTimeInput,
    RoundingLoss,
    TaskSpec,
    utc_instant,
)

SLOT = timedelta(minutes=15)


def resolve_local_time(local: datetime, timezone: str, fold: int | None = None) -> datetime:
    """Reject gaps and require an explicit selection for a repeated wall time."""
    if local.tzinfo is not None:
        return utc_instant(local)
    if fold not in (None, 0, 1):
        raise ValueError("fold must be 0 or 1")
    zone = ZoneInfo(timezone)
    choices = {}
    for selected in (0, 1):
        candidate = local.replace(tzinfo=zone, fold=selected).astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == local:
            choices[selected] = candidate
    if not choices:
        raise ValueError("NONEXISTENT_LOCAL_TIME: select a real local instant")
    if len(set(choices.values())) > 1 and fold is None:
        raise ValueError("AMBIGUOUS_LOCAL_TIME: select offset or fold")
    return choices[fold if fold is not None else 0]


def _instant(value, timezone: str, fold: int | None = None) -> datetime:
    if isinstance(value, dict):
        return _instant(value["local"], value.get("timezone", timezone), value.get("fold"))
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return resolve_local_time(parsed, timezone, fold)


def _union(ranges):
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)


def normalize_time_inputs(raw: dict, now: datetime) -> InputSnapshot:
    """Build a content-addressed snapshot; slot zero is this UTC date's midnight.

    Raw intervals have start/end instants. Local instants may be supplied as
    {local, timezone, fold}; all original deadline intent and rounding losses
    remain visible. Availability is not invented when none is entered.
    """
    now = utc_instant(now)
    timezone = raw.get("timezone", "UTC")
    zone = ZoneInfo(timezone)
    origin = datetime.combine(now.date(), time.min, UTC)
    end_date = now.astimezone(zone).date() + timedelta(days=14)
    horizon_end = resolve_local_time(datetime.combine(end_date, time.min), timezone)
    losses = []
    originals = []

    def entered(value, field):
        local = value.get("local") if isinstance(value, dict) else value
        originals.append(
            OriginalTimeInput(
                field=field,
                value=local.isoformat() if isinstance(local, datetime) else str(local),
                timezone=value.get("timezone", timezone) if isinstance(value, dict) else timezone,
                fold=value.get("fold") if isinstance(value, dict) else None,
            )
        )
        return _instant(value, timezone)

    def slot(instant, direction, field):
        quotient = (instant - origin) / SLOT
        index = math.ceil(quotient) if direction == "up" else math.floor(quotient)
        rounded = origin + index * SLOT
        if rounded != instant:
            losses.append(
                RoundingLoss(
                    field=field,
                    original=instant,
                    rounded=rounded,
                    seconds=abs((rounded - instant).total_seconds()),
                )
            )
        return index

    cutoff = slot(now, "up", "reference_now")
    end_slot = slot(horizon_end, "down", "horizon_end")

    def intervals(items, outward, field):
        ranges = []
        for index, item in enumerate(items):
            start = entered(item["start"], f"{field}.{index}.start")
            end = entered(item["end"], f"{field}.{index}.end")
            if start >= end:
                raise ValueError("interval end must follow start")
            a = slot(start, "down" if outward else "up", f"{field}.{index}.start")
            b = slot(end, "up" if outward else "down", f"{field}.{index}.end")
            ranges.append((max(cutoff, a), min(end_slot, b)))
        return _union(ranges)

    availability = intervals(raw.get("availability", ()), False, "availability")
    busy = intervals(raw.get("fixed_events", ()), True, "fixed_events")
    preferred = intervals(raw.get("preferred_windows", ()), False, "preferred_windows")
    first = end_slot
    for a, b in availability:
        point = a
        for busy_a, busy_b in busy:
            if busy_a <= point < busy_b:
                point = busy_b
        if point < b:
            first = point
            break
    owner = UUID(str(raw["owner_id"]))
    tasks = []
    for item in raw.get("tasks", ()):
        data = dict(item)
        if "required_slots" in data:
            raise ValueError("required_slots is derived and cannot be supplied")
        if {"release_slot", "deadline_slot", "deadline_at"}.intersection(data):
            raise ValueError("raw forms cannot supply derived solver fields")
        data.setdefault("owner_id", owner)
        release = (
            entered(data["release_at"], f"task.{data['id']}.release_at")
            if data.get("release_at")
            else None
        )
        data["release_at"] = release
        data["release_slot"] = (
            max(cutoff, slot(release, "up", f"task.{data['id']}.release_at")) if release else cutoff
        )
        if data.get("deadline"):
            deadline_data = dict(data["deadline"])
            deadline_data.setdefault("timezone", timezone)
            deadline = Deadline(**deadline_data)
            if deadline.kind == "DATE":
                next_day = date.fromisoformat(deadline.value) + timedelta(days=1)
                due = resolve_local_time(
                    datetime.combine(next_day, time.min), deadline.timezone, deadline.fold
                )
            else:
                due = _instant(deadline.value, deadline.timezone, deadline.fold)
            data.update(
                deadline=deadline,
                deadline_at=due,
                deadline_slot=slot(due, "down", f"task.{data['id']}.deadline"),
            )
        tasks.append(TaskSpec(**data))
    protected = []
    for item in raw.get("protected_blocks", ()):
        if item.get("source") == "COMPLETED":
            continue
        if not item.get("end"):
            raise ValueError("EXPECTED_END_REQUIRED")
        start = entered(item["start"], f"protected.{item['id']}.start")
        end = entered(item["end"], f"protected.{item['id']}.end")
        if (
            item.get("locked")
            and item.get("source") != "CALENDAR_OFF_GRID"
            and ((start - origin) % SLOT or (end - origin) % SLOT)
        ):
            raise ValueError("LOCK_NOT_GRID_ALIGNED")
        if end <= start:
            raise ValueError("protected interval needs an explicit expected end after start")
        if end <= now:
            continue
        a = max(cutoff, slot(start, "down", "protected.start"))
        b = slot(end, "up", "protected.end")
        data = dict(item)
        data.update(
            owner_id=item.get("owner_id", owner),
            start=origin + a * SLOT,
            end=origin + b * SLOT,
            start_slot=a,
            end_slot=b,
            original_start=start,
        )
        protected.append(Block(**data))
    dependencies = tuple(
        Dependency(
            owner_id=item.get("owner_id", owner),
            predecessor_id=item["predecessor_id"],
            successor_id=item["successor_id"],
        )
        for item in raw.get("dependencies", ())
    )
    snapshot = InputSnapshot(
        id=UUID(int=0),
        snapshot_hash="",
        owner_id=owner,
        planning_revision=raw.get("planning_revision", 0),
        reference_now=now,
        timezone=timezone,
        slot_origin=origin,
        horizon_start=origin + first * SLOT,
        horizon_end=horizon_end,
        horizon_start_slot=first,
        horizon_end_slot=end_slot,
        tasks=tuple(sorted(tasks, key=lambda task: str(task.id))),
        dependencies=dependencies,
        availability=availability,
        busy_slot_ranges=busy,
        protected_blocks=tuple(protected),
        preferred_windows=preferred,
        prior_candidate=raw.get("prior_candidate"),
        prior_active_candidate_id=raw.get("prior_active_candidate_id"),
        objective_version=raw.get("objective_version", "v1"),
        rounding_losses=tuple(losses),
        original_time_inputs=tuple(originals),
    )
    payload = snapshot.model_dump(mode="json", exclude={"id", "snapshot_hash"})
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return snapshot.model_copy(update={"id": UUID(hex=digest[:32]), "snapshot_hash": digest})


def preview_timezone_change(raw: dict, timezone: str, now: datetime) -> InputSnapshot:
    """Return a detached preview; activating a changed timezone is a command concern."""
    preview = deepcopy(raw)
    old_zone = raw.get("timezone", "UTC")
    for field in ("fixed_events", "protected_blocks"):
        for item in preview.get(field, ()):
            item["start"] = _instant(item["start"], old_zone)
            item["end"] = _instant(item["end"], old_zone)
    for task in preview.get("tasks", ()):
        if task.get("release_at"):
            task["release_at"] = _instant(task["release_at"], old_zone)
        deadline = task.get("deadline")
        if deadline:
            if deadline["kind"] == "DATE":
                deadline["timezone"] = timezone
            else:
                deadline["value"] = _instant(
                    deadline["value"], deadline.get("timezone", old_zone), deadline.get("fold")
                ).isoformat()
    preview["timezone"] = timezone
    return normalize_time_inputs(preview, now)
