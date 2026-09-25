"""Preview civil-date changes while preserving existing absolute commitments."""

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from planner.db.models import Availability, FixedEvent, Identity, PlanningState, Task
from planner.domain.time_rules import resolve_local_time


def absolute(value, timezone):
    if isinstance(value, dict):
        return resolve_local_time(
            datetime.fromisoformat(value["local"]),
            value.get("timezone", timezone),
            value.get("fold"),
        ).isoformat()
    return resolve_local_time(datetime.fromisoformat(value), timezone).isoformat()


def preview_timezone(db, owner_id, timezone):
    ZoneInfo(timezone)
    identity = db.get(Identity, owner_id)
    revision = db.get(PlanningState, owner_id).revision
    old = identity.timezone
    tasks = db.scalars(select(Task).where(Task.owner_id == owner_id).order_by(Task.id)).all()
    dates, updates = [], []
    for task in tasks:
        details = deepcopy(task.details)
        if details.get("release_at"):
            details["release_at"] = absolute(details["release_at"], old)
        deadline = details.get("deadline")
        if deadline and deadline["kind"] == "DATE":
            midnight = datetime.combine(
                date.fromisoformat(deadline["value"]) + timedelta(days=1), time.min
            )
            dates.append(
                {
                    "task_id": str(task.id),
                    "title": task.title,
                    "date": deadline["value"],
                    "old_bound": resolve_local_time(
                        midnight, deadline.get("timezone", old), deadline.get("fold")
                    ).isoformat(),
                    "new_bound": resolve_local_time(midnight, timezone).isoformat(),
                }
            )
            details["deadline"] = {**deadline, "timezone": timezone, "fold": None}
        elif deadline:
            instant = resolve_local_time(
                datetime.fromisoformat(deadline["value"]),
                deadline.get("timezone", old),
                deadline.get("fold"),
            )
            details["deadline"] = {
                **deadline,
                "value": instant.isoformat(),
                "timezone": "UTC",
                "fold": None,
            }
        updates.append((task, details))
    events = db.scalars(
        select(FixedEvent).where(FixedEvent.owner_id == owner_id).order_by(FixedEvent.id)
    ).all()
    fixed = [
        (event, {key: absolute(event.details[key], old) for key in ("start", "end")})
        for event in events
    ]
    availability = db.get(Availability, owner_id)
    windows = [
        {key: absolute(window[key], old) for key in ("start", "end")}
        for window in (availability.windows if availability else [])
    ]
    preview = {
        "old_timezone": old,
        "timezone": timezone,
        "revision": revision,
        "date_deadlines": dates,
        "preserved_fixed_events": len(events),
        "preserved_available_windows": len(windows),
        "weekly_rules_follow_new_timezone": True,
    }
    digest = hashlib.sha256(
        json.dumps({**preview, "owner_id": str(owner_id)}, sort_keys=True).encode()
    ).hexdigest()
    return {**preview, "preview_hash": digest}, (identity, updates, fixed, availability, windows)


def apply_timezone(db, owner_id, timezone, updates, now):
    from planner.api.errors import APIError
    from planner.domain.task_rules import validate_tasks
    from planner.jobs.dispatcher import capture_snapshot

    identity, tasks, events, availability, windows = updates
    identity.timezone = timezone
    for task, details in tasks:
        task.details = details
    for event, details in events:
        event.details = details
    if availability:
        availability.windows = windows
    db.flush()
    # Existing weekday prohibitions and protected commitments must remain explicit.
    snapshot = capture_snapshot(db, owner_id, now)
    if any(v.code == "PROTECTED_BUSY_CONFLICT" for v in validate_tasks(snapshot)):
        raise APIError(
            "PROTECTED_BUSY_CONFLICT",
            409,
            "Move or unlock protected work before changing its weekly rules "
            "through a timezone change.",
        )
