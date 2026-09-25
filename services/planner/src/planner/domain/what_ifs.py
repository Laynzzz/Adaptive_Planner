"""Apply only explicitly selected hypothetical input fields."""

from copy import deepcopy


def change_inputs(raw: dict, changes: dict) -> dict:
    preview = deepcopy(raw)
    tasks = {str(task["id"]): task for task in preview["tasks"]}
    for patch in changes.get("task_changes", ()):
        target = tasks.get(str(patch["task_id"]))
        if target is None:
            raise ValueError("WHAT_IF_TASK_NOT_FOUND")
        for key in ("remaining_minutes", "deadline"):
            if key in patch:
                target[key] = patch[key]
    preview["availability"] = [
        *preview.get("availability", ()),
        *changes.get("additional_availability", ()),
    ]
    return preview
