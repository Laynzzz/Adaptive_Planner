"""Build supervised rows only from validated measured algorithm outcomes."""

import argparse
import hashlib
import json
from pathlib import Path

from planner.ml.features import FEATURE_NAMES, FEATURE_VERSION


def label_case(greedy, reference, tolerance=0.02):
    if not greedy.get("validated") or greedy.get("quality") is None:
        return {
            "label": None,
            "label_reason": "GREEDY_INVALID_OR_MISSING",
            "measured_improvement": None,
        }
    if not reference.get("validated") or reference.get("quality") is None:
        return {"label": None, "label_reason": "REFERENCE_MISSING", "measured_improvement": None}
    improvement = reference["quality"] - greedy["quality"]
    if improvement > tolerance:
        return {
            "label": True,
            "label_reason": "VALIDATED_REFERENCE_IMPROVES",
            "measured_improvement": improvement,
        }
    if reference.get("proof") in ("CP_SAT_OPTIMAL", "EXHAUSTIVE_TINY"):
        return {
            "label": False,
            "label_reason": "PROVEN_WITHIN_TOLERANCE",
            "measured_improvement": improvement,
        }
    return {
        "label": None,
        "label_reason": "REFERENCE_SEARCH_CENSORED",
        "measured_improvement": improvement,
    }


def build_row(row, tolerance=0.02):
    greedy_runs = sorted(
        (x for x in row["results"] if x["policy"] == "greedy"), key=lambda x: x["repeat"]
    )
    greedy = greedy_runs[0] if greedy_runs else {"validated": False, "quality": None}
    candidates = [row["reference"], *row["results"]]
    valid = [
        result
        for result in candidates
        if result.get("validated") and result.get("quality") is not None
    ]
    best = max(valid, key=lambda r: r["quality"]) if valid else row["reference"]
    reference = {
        **best,
        "selection": "best valid result from measured reference and repeated baseline runs",
        "requested_reference": row["reference"],
    }
    return {
        **{
            name: row[name]
            for name in (
                "scenario_id",
                "group_id",
                "split",
                "seed",
                "family",
                "parameters",
                "known_feasible",
                "feasibility_provenance",
                "generator_version",
            )
        },
        "schema_version": "routing-dataset-v1",
        "snapshot": row["snapshot"],
        "features": greedy.get("features"),
        "greedy": greedy,
        "reference": reference,
        "policy_results": row["results"],
        "quality_tolerance": tolerance,
        **label_case(greedy, reference, tolerance),
    }


def load_rows(path):
    """Read raw measurement groups or derived rows; never discard unknown outcomes."""
    path = Path(path)
    records = (
        [json.loads(item.read_text(encoding="utf-8")) for item in sorted(path.glob("[0-9]*.json"))]
        if path.is_dir()
        else [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    )
    return [
        record if record.get("schema_version") == "routing-dataset-v1" else build_row(record)
        for record in records
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/training/v2"))
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument(
        "--measurement-manifest", type=Path, default=Path("benchmarks/manifests/full.json")
    )
    args = parser.parse_args()
    if args.input.is_dir():
        rows = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(args.input.glob("[0-9]*.json"))
        ]
    else:
        rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines()]
    groups = [row["group_id"] for row in rows]
    if len(groups) != len(set(groups)):
        raise SystemExit("Duplicate base group; repeated runs belong inside one row")
    counts = {
        split: sum(row["split"] == split for row in rows)
        for split in ("train", "validation", "test")
    }
    if not args.allow_partial and counts != {"train": 600, "validation": 200, "test": 200}:
        raise SystemExit("Incomplete release; use --allow-partial for development samples only")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for split in counts:
        path = args.output_dir / f"{split}.jsonl"
        if path.exists():
            raise SystemExit("Output exists; choose a new directory to preserve dataset provenance")
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                if row["split"] == split:
                    stream.write(json.dumps(build_row(row), sort_keys=True) + "\n")
        artifacts[split] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "groups": counts[split],
        }
    measurement = json.loads(args.measurement_manifest.read_text(encoding="utf-8"))
    limitations = measurement.get("measurement_limitations")
    if limitations is None:
        limitations = (
            ["WINDOWS_CHILD_TREE_DEADLINE_NOT_ENFORCED_V2"]
            if measurement.get("version") == "scheduler-benchmark-v2"
            else ["MEASUREMENT_SUPERVISION_UNVERIFIED"]
        )
    manifest = {
        "version": "routing-dataset-v1",
        "partial": args.allow_partial,
        "source": str(args.input),
        "measurement_manifest_sha256": hashlib.sha256(
            args.measurement_manifest.read_bytes()
        ).hexdigest(),
        "measurement_version": measurement.get("version"),
        "measurement_limitations": limitations,
        "deployment_eligibility": (
            "DENIED_MEASUREMENT_SUPERVISION_LIMIT" if limitations else "REQUIRES_ALL_POLICY_GATES"
        ),
        "feature_version": FEATURE_VERSION,
        "feature_order": FEATURE_NAMES,
        "artifacts": artifacts,
        "label_rule": (
            "Measured valid reference improvement >0.02; negatives require "
            "proven optimum; others unknown"
        ),
        "missing_results": (
            "Retained in each policy_results list, never imputed as successful or zero latency"
        ),
        "provenance": (
            "Actual local frozen solver executions on AI-assisted synthetic witnessed workloads"
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "manifest": str(args.output_dir / "manifest.json"),
                "counts": counts,
                "partial": args.allow_partial,
            }
        )
    )


if __name__ == "__main__":
    main()
