"""Independent deterministic reference checks; these do not replace human semantic review."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from planner.ai.prompt import PROMPT_HASH, SCHEMA_HASH

DATA = Path(__file__).parent
REPO = DATA.parents[1]


def validate_reference(row):
    reference = row["reference"]
    fields = reference["fields"]
    keys = {path.split(".")[1] for path in fields}
    edges = {}
    assert len(row["text"]) <= 8000 and len(keys) <= 20
    for path, field in fields.items():
        group, key, name = path.split(".")
        assert group == "tasks" and re.fullmatch(r"task_[1-9][0-9]*", key)
        value = field["value"]
        assert field["label"] in ("unknown", "inferred", "explicit")
        if field["label"] == "unknown":
            assert value is None and path in reference["required_clarifications"]
        if name == "title":
            assert value and value in row["text"]
        elif name == "remaining_minutes" and value is not None:
            assert isinstance(value, int) and 0 < value < 2147483648
            if field["label"] == "explicit":
                matches = re.findall(r"(\d+)\s*(minutes?|mins?|hours?|hrs?)", row["text"])
                assert value in [
                    int(n) * (60 if units.startswith("h") else 1) for n, units in matches
                ]
        elif name == "deadline" and value is not None:
            assert value["kind"] == "DATE"
            date.fromisoformat(value["value"])
            if field["label"] == "explicit":
                assert value["value"] in row["text"]
        elif name == "priority":
            assert 1 <= value <= 5
        elif name == "predecessor_keys":
            assert set(value).issubset(keys)
            edges[key] = value

    def visit(key, ancestors):
        assert key not in ancestors, "Reference dependency cycle"
        for parent in edges.get(key, []):
            visit(parent, {*ancestors, key})

    for key in keys:
        visit(key, set())
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for constraint in reference["constraints"]:
        assert weekdays[constraint["weekday"]] in row["text"].lower()
        assert constraint["kind"] in ("SOFT_AVOID", "HARD_UNAVAILABLE", "HARD_NO_DEADLINE")


def load_frozen():
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["prompt_hash"] == PROMPT_HASH, "Frozen prompt changed"
    assert manifest["schema_hash"] == SCHEMA_HASH, "Frozen schema changed"
    assert (
        manifest["model_config_hash"]
        == hashlib.sha256(json.dumps(manifest["model_config"], sort_keys=True).encode()).hexdigest()
    )
    for path, digest in manifest.get("implementation_hashes", {}).items():
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == digest, (
            f"Frozen source changed: {path}"
        )
    splits, seen_ids, seen_families = {}, set(), set()
    for split in ("dev", "validation", "test"):
        path = DATA / f"{split}.jsonl"
        spec = manifest["files"][path.name]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"], (
            "Frozen data changed"
        )
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == spec["examples"] == (60 if split == "dev" else 30)
        families = {row["family"] for row in rows}
        assert len(families) == spec["families"] and not families & seen_families
        seen_families.update(families)
        for row in rows:
            assert row["split"] == split and row["id"] not in seen_ids
            seen_ids.add(row["id"])
            assert row["provenance"]["independent_human_review"] == "PENDING"
            validate_reference(row)
        splits[split] = rows
    return manifest, splits
