"""Expand reviewed weekday rules through the existing immutable snapshot contract."""

from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from planner.api.errors import APIError
from planner.db.models import Identity, Task
from planner.db.weekday_models import WeekdayRule
from planner.domain.contracts import Deadline
from planner.domain.time_rules import resolve_local_time


def rules_for(db, owner_id):
    return list(
        db.scalars(
            select(WeekdayRule)
            .where(WeekdayRule.owner_id == owner_id)
            .order_by(WeekdayRule.kind, WeekdayRule.weekday)
        )
    )


def deadline_weekday(deadline, timezone):
    parsed = Deadline.model_validate(deadline)
    if parsed.kind == "DATE":
        # A date-only Friday means Friday, though its exclusive bound is Saturday.
        return date.fromisoformat(parsed.value).weekday()
    instant = resolve_local_time(datetime.fromisoformat(parsed.value), parsed.timezone, parsed.fold)
    return instant.astimezone(ZoneInfo(timezone)).weekday()


def assert_deadline_allowed(db, owner_id, data, *, rules=None):
    if not data.get("deadline") or data.get("state") in ("DONE", "CANCELLED"):
        return
    rules = rules if rules is not None else rules_for(db, owner_id)
    forbidden = {rule.weekday for rule in rules if rule.kind == "HARD_NO_DEADLINE"}
    timezone = db.get(Identity, owner_id).timezone
    if deadline_weekday(data["deadline"], timezone) in forbidden:
        raise APIError(
            "DEADLINE_WEEKDAY_FORBIDDEN",
            409,
            "The deadline falls on a forbidden weekday. Change the deadline or remove the rule.",
        )


def expand_weekday_rules(raw, rules, now):
    """Local civil days use actual UTC boundaries, including 23/25-hour DST days."""
    result = deepcopy(raw)
    kinds = {
        kind: {weekday for selected, weekday in rules if selected == kind}
        for kind in ("SOFT_AVOID", "HARD_UNAVAILABLE", "HARD_NO_DEADLINE")
    }
    timezone = raw.get("timezone", "UTC")
    start_date = now.astimezone(ZoneInfo(timezone)).date()
    preferred = []
    fixed = list(result.get("fixed_events", []))
    for offset in range(14):
        day = start_date + timedelta(days=offset)
        start = resolve_local_time(datetime.combine(day, time.min), timezone)
        end = resolve_local_time(datetime.combine(day + timedelta(days=1), time.min), timezone)
        interval = {"start": start.astimezone(UTC), "end": end.astimezone(UTC)}
        if day.weekday() in kinds["HARD_UNAVAILABLE"]:
            fixed.append(interval)
        if kinds["SOFT_AVOID"] and day.weekday() not in kinds["SOFT_AVOID"]:
            preferred.append(interval)
    result["fixed_events"] = fixed
    if kinds["SOFT_AVOID"]:
        result["preferred_windows"] = preferred
    return result


def apply_weekday_rules(db, owner_id, raw, now):
    rules = rules_for(db, owner_id)
    for task in raw["tasks"]:
        assert_deadline_allowed(db, owner_id, task, rules=rules)
    return expand_weekday_rules(raw, [(r.kind, r.weekday) for r in rules], now)


def accept_weekday_rule(db, owner_id, kind, weekday, now):
    if kind not in ("SOFT_AVOID", "HARD_UNAVAILABLE", "HARD_NO_DEADLINE") or not 0 <= weekday <= 6:
        raise APIError("INVALID_WEEKDAY_RULE", 422, "Choose a rule kind and weekday.")
    existing = rules_for(db, owner_id)
    for rule in existing:
        if (rule.kind, rule.weekday) == (kind, weekday):
            return rule.id
    proposed = WeekdayRule(owner_id=owner_id, kind=kind, weekday=weekday)
    if kind == "SOFT_AVOID" and len({r.weekday for r in existing if r.kind == kind}) == 6:
        raise APIError("PREFERRED_WEEKDAY_REQUIRED", 422, "Leave at least one preferred weekday.")
    for task in db.scalars(select(Task).where(Task.owner_id == owner_id)):
        assert_deadline_allowed(
            db, owner_id, {**task.details, "state": task.state}, rules=[*existing, proposed]
        )
    db.add(proposed)
    db.flush()
    if kind == "HARD_UNAVAILABLE":
        from planner.domain.task_rules import validate_tasks
        from planner.jobs.dispatcher import capture_snapshot

        if any(
            v.code == "PROTECTED_BUSY_CONFLICT"
            for v in validate_tasks(capture_snapshot(db, owner_id, now))
        ):
            raise APIError(
                "PROTECTED_BUSY_CONFLICT",
                409,
                "Unlock or move protected work before making its weekday unavailable.",
            )
    return proposed.id
