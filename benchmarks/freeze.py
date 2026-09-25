"""Freeze executable Python sources so parallel project work cannot alter a run."""

import hashlib
import json
import shutil
from pathlib import Path


def main():
    frozen = Path(".runtime/benchmarks/frozen-v3")
    if frozen.exists():
        raise SystemExit("Frozen source release already exists")
    frozen.mkdir(parents=True)
    for source, target in (
        (Path("services/planner/src/planner"), frozen / "planner"),
        (Path("benchmarks"), frozen / "benchmarks"),
    ):
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "manifests"))
    hashes = {
        str(path).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(frozen.rglob("*.py"))
    }
    manifest = {
        "version": "scheduler-benchmark-v3",
        "generator_version": "scheduler-scenarios-v1",
        "seed": 20260925,
        "repeats": 2,
        "policies": ["greedy", "cp_sat", "warm_cp_sat"],
        "policy_wall_ms": 2000,
        "cp_budget_ms": 200,
        "reference_wall_ms": 4000,
        "reference_budget_ms": 600,
        "workers": 2,
        "max_runtime_seconds": 5400,
        "scenario_ids": list(range(1000)),
        "output": ".runtime/benchmarks/full-v3.jsonl",
        "frozen_path": str(frozen).replace("\\", "/"),
        "source_hashes": hashes,
        "split_counts": {"train": 600, "validation": 200, "test": 200},
        "quality_tolerance": 0.02,
        "measurement_limitations": [],
        "supervision": "Windows atomic kill-on-close Job Object / POSIX process session",
        "prior_release": "v2 retained for audit; descendant deadline flaw denies promotion",
        "clock": "2026-09-25T00:00:00+00:00",
        "label_rule": (
            "Measured best-known improvement above tolerance; no-improvement "
            "censored unless reference optimum proven"
        ),
        "test_policy": (
            "Sealed final groups; no final per-case inspection before "
            "model/router configuration freeze"
        ),
        "reference_claim": (
            "600ms native search is best-known only; OPTIMAL or tiny enumeration required for proof"
        ),
        "zero_budget_controls": (
            "Named zero-budget families deliberately retain unknown search outcomes"
        ),
        "synthetic_provenance": (
            "AI-assisted generator; feasibility witnessed and checked by "
            "independent production validator"
        ),
    }
    Path("benchmarks/manifests/full-v3.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    smoke = {
        **manifest,
        "scenario_ids": [0, 4, 5, 6, 7, 23, 24],
        "repeats": 1,
        "output": ".runtime/benchmarks/smoke-v3.jsonl",
    }
    Path("benchmarks/manifests/smoke-v3.json").write_text(
        json.dumps(smoke, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"frozen": str(frozen), "source_files": len(hashes)}))


if __name__ == "__main__":
    main()
