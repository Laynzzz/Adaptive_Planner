"""Apply only the selected, explicitly reviewed task fields in one command transaction."""

import json
import re
from uuid import uuid5

from pydantic import ValidationError
from sqlalchemy import func, select

from planner.ai.interpret import parse_proposal
from planner.api.errors import APIError
from planner.api.schemas import TaskFields
from planner.db.ai_models import InterpretationRecord
from planner.db.models import DependencyEdge, Task
from planner.domain.time_rules import normalize_time_inputs
from planner.domain.weekday_rules import accept_weekday_rule, assert_deadline_allowed


def accept_in_transaction(
    db, owner_id, interpretation_id, selected_keys, confirmed_fields, overrides, *, now,
    selected_constraint_keys=None
):
    record = db.scalar(
        select(InterpretationRecord).where(
            InterpretationRecord.id == interpretation_id, InterpretationRecord.owner_id == owner_id
        )
    )
    if record is None:
        raise APIError("NOT_FOUND", 404, "Interpretation not found.")
    if record.state != "READY":
        raise APIError(
            "INTERPRETATION_NOT_READY", 409, "Review a ready interpretation before accepting it."
        )
    try:
        proposal = parse_proposal(json.dumps(record.proposal), record.source_text)
    except (ValueError, KeyError):
        raise APIError(
            "MODEL_OUTPUT_INVALID", 422, "The proposal failed semantic validation."
        ) from None
    if proposal.constraints and selected_constraint_keys is None:
        raise APIError("CONSTRAINT_REVIEW_REQUIRED", 422,
                       "Explicitly select or deselect the proposed weekday rules.")
    selected_rules = set(selected_constraint_keys or ())
    rules = {rule.key: rule for rule in proposal.constraints}
    if (len(rules) != len(proposal.constraints)
            or len(selected_rules) != len(selected_constraint_keys or ())
            or not selected_rules.issubset(rules)):
        raise APIError("SELECTION_INVALID", 422, "Select each proposed rule at most once.")
    if proposal.abstained or not (selected_keys or selected_rules):
        raise APIError("CLARIFICATION_REQUIRED", 422, "Select at least one proposed task or rule.")
    for key in selected_rules:
        rule = rules[key]
        evidence = " ".join(span.text.lower() for span in rule.evidence)
        weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[rule.weekday]
        cues = {"SOFT_AVOID": r"\b(dislike|prefer|avoid|rather)\b",
                "HARD_UNAVAILABLE": r"\b(cannot|can't|unavailable|must not|never|no work|not available)\b",
                "HARD_NO_DEADLINE": r"\b(no deadlines?|no due dates?|deadlines? (?:must not|cannot|can't|not)|not due)\b"}
        if (rule.label == "unknown" or not re.search(cues[rule.kind], evidence)
                or not re.search(r"\b" + weekday + r"\b", evidence)):
            raise APIError("CONSTRAINT_UNSUPPORTED", 422,
                           "The rule lacks supported source evidence; use the explicit rule form.")
        if f"constraints.{key}" not in confirmed_fields:
            raise APIError("CONFIRMATION_REQUIRED", 422, "Confirm every selected weekday rule.")
    tasks = {task.key: task for task in proposal.tasks}
    selected = set(selected_keys)
    if len(selected) != len(selected_keys) or not selected.issubset(tasks):
        raise APIError("SELECTION_INVALID", 422, "Select only proposed task keys, once each.")
    allowed = {
        f"tasks.{key}.{field}"
        for key in selected
        for field in ("title", "remaining_minutes", "deadline", "priority")
    }
    if not set(overrides).issubset(allowed) or not set(confirmed_fields).issubset(
        allowed | {f"constraints.{key}" for key in selected_rules}
    ):
        raise APIError(
            "REVIEW_FIELDS_INVALID", 422, "Review fields must refer to selected proposed tasks."
        )
    all_paths = {
        f"tasks.{key}.{name}"
        for key in tasks
        for name in ("title", "remaining_minutes", "deadline", "priority")
    }
    for path in proposal.unresolved_fields:
        if path not in all_paths or (path in allowed and path not in overrides):
            raise APIError(
                "CLARIFICATION_REQUIRED",
                422,
                "Resolve the proposal's contradictions and selected unknown fields.",
            )
    count = db.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.owner_id == owner_id, Task.state.notin_(["DONE", "CANCELLED"]))
    )
    if count + len(selected) > 200:
        raise APIError("ACTIVE_TASK_LIMIT", 422, "At most 200 active tasks are supported.")
    resolved = []
    ids = {key: uuid5(record.id, key) for key in selected}
    for key in selected_keys:
        task = tasks[key]
        if not set(task.predecessor_keys).issubset(selected):
            raise APIError(
                "DEPENDENCY_SELECTION_REQUIRED", 422, "Select all referenced predecessors."
            )
        fields = {}
        for name in ("title", "remaining_minutes", "deadline", "priority"):
            extracted = getattr(task, name)
            path = f"tasks.{key}.{name}"
            if path in overrides:
                value = overrides[path]
            elif extracted.label == "unknown":
                raise APIError(
                    "CLARIFICATION_REQUIRED", 422, "Resolve every unknown selected field."
                )
            elif extracted.requires_confirmation and path not in confirmed_fields:
                raise APIError(
                    "CONFIRMATION_REQUIRED", 422, "Confirm each inferred selected field."
                )
            else:
                value = (
                    extracted.value.model_dump(mode="json")
                    if hasattr(extracted.value, "model_dump")
                    else extracted.value
                )
            fields[name] = value
        try:
            parsed = TaskFields.model_validate(fields)
            data = parsed.model_dump(mode="json")
            normalize_time_inputs(
                {
                    "owner_id": str(owner_id),
                    "timezone": record.timezone,
                    "tasks": [{"id": str(ids[key]), **data}],
                },
                now,
            )
        except (ValueError, KeyError, OverflowError, ValidationError):
            raise APIError(
                "REVIEW_VALUE_INVALID", 422, "The reviewed task values are invalid."
            ) from None
        assert_deadline_allowed(db, owner_id, data)
        resolved.append((key, data))
    for key, data in resolved:
        db.add(
            Task(
                id=ids[key],
                owner_id=owner_id,
                title=data["title"],
                remaining_minutes=data["remaining_minutes"],
                priority=data["priority"],
                state="TODO",
                details={
                    k: v
                    for k, v in data.items()
                    if k not in ("title", "remaining_minutes", "priority")
                },
            )
        )
    db.flush()
    for key in selected_keys:
        for predecessor in tasks[key].predecessor_keys:
            db.add(
                DependencyEdge(
                    owner_id=owner_id, predecessor_id=ids[predecessor], successor_id=ids[key]
                )
            )
    rule_ids = [str(accept_weekday_rule(db, owner_id, rules[key].kind, rules[key].weekday, now))
                for key in (selected_constraint_keys or ())]
    record.state = "ACCEPTED"
    record.accepted_task_ids = [str(ids[key]) for key in selected_keys]
    return {"task_ids": record.accepted_task_ids, "weekday_rule_ids": rule_ids,
            "interpretation_id": str(record.id)}
