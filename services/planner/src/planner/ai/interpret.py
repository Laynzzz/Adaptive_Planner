"""Validate provider output against source evidence and domain semantics."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from planner.ai.schema import ExtractionDraft


def parse_proposal(payload: str, source_text: str) -> ExtractionDraft:
    if len(source_text) > 8000 or len(payload) > 150000:
        raise ValueError("INPUT_LIMIT")
    proposal = ExtractionDraft.model_validate_json(payload)
    keys = [task.key for task in proposal.tasks]
    if len(keys) != len(set(keys)):
        raise ValueError("DUPLICATE_TASK_KEY")
    graph = {}
    unresolved = set(proposal.unresolved_fields)
    for task in proposal.tasks:
        graph[task.key] = task.predecessor_keys
        if any(key not in keys for key in task.predecessor_keys):
            raise ValueError("DEPENDENCY_UNKNOWN")
        for name in ("title", "remaining_minutes", "deadline", "priority"):
            item = getattr(task, name)
            for span in item.evidence:
                if source_text[span.start : span.end] != span.text or span.end > len(source_text):
                    raise ValueError("EVIDENCE_INVALID")
            if item.label == "unknown":
                unresolved.add(f"tasks.{task.key}.{name}")
        if task.title.value is not None and (
            not task.title.value.strip() or len(task.title.value) > 500
        ):
            raise ValueError("TITLE_INVALID")
        if (
            task.remaining_minutes.value is not None
            and not 1 <= task.remaining_minutes.value <= 2147483647
        ):
            raise ValueError("DURATION_INVALID")
        if task.priority.value is not None and not 1 <= task.priority.value <= 5:
            raise ValueError("PRIORITY_INVALID")
        if task.deadline.value is not None:
            deadline = task.deadline.value
            ZoneInfo(deadline.timezone)
            if deadline.kind == "DATE":
                date.fromisoformat(deadline.value)
            else:
                datetime.fromisoformat(deadline.value)
    visiting, visited = set(), set()

    def visit(key):
        if key in visiting:
            raise ValueError("DEPENDENCY_CYCLE")
        if key not in visited:
            visiting.add(key)
            for parent in graph[key]:
                visit(parent)
            visiting.remove(key)
            visited.add(key)

    for key in keys:
        visit(key)
    for constraint in proposal.constraints:
        for span in constraint.evidence:
            if source_text[span.start : span.end] != span.text or span.end > len(source_text):
                raise ValueError("EVIDENCE_INVALID")
        evidence = " ".join(span.text.lower() for span in constraint.evidence)
        soft = bool(re.search(r"\b(dislike|prefer|rather|avoid if possible)\b", evidence))
        if soft and constraint.kind != "SOFT_AVOID":
            raise ValueError("HARD_SOFT_CONTRADICTION")
        if not constraint.requires_confirmation:
            raise ValueError("CONSTRAINT_CONFIRMATION_REQUIRED")
    return proposal.model_copy(update={"unresolved_fields": tuple(sorted(unresolved))})
