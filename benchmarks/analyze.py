"""Summarize measured baselines without hiding missing or invalid outcomes."""

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def distribution(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return {"n": 0, "p50": None, "p95": None, "mean": None}
    return {
        "n": len(values),
        "p50": statistics.median(values),
        "p95": values[max(0, math.ceil(len(values) * 0.95) - 1)],
        "mean": statistics.mean(values),
    }


def summarize_policy(rows, policy):
    runs = [
        (row, result) for row in rows for result in row["results"] if result["policy"] == policy
    ]
    valid = [(row, result) for row, result in runs if result.get("validated")]
    losses, signed = [], []
    for row, result in valid:
        references = [row["reference"], *row["results"]]
        qualities = [
            r["quality"] for r in references if r.get("validated") and r.get("quality") is not None
        ]
        if qualities and result.get("quality") is not None:
            delta = max(qualities) - result["quality"]
            signed.append(delta)
            losses.append(max(0, delta))
    tail = sorted(losses, reverse=True)[: max(1, math.ceil(len(losses) / 10))]
    return {
        "runs": len(runs),
        "completed_valid": len(valid),
        "invalid": sum(bool(result.get("invalid")) for _, result in runs),
        "missing_or_invalid": len(runs) - len(valid),
        "statuses": dict(Counter(result.get("status", "MISSING") for _, result in runs)),
        "known_feasible_runs": sum(row["known_feasible"] for row, _ in runs),
        "known_feasible_completed": sum(row["known_feasible"] for row, _ in valid),
        "paired_quality": {
            "n": len(losses),
            "mean_positive_loss": statistics.mean(losses) if losses else None,
            "mean_signed_reference_minus_policy": statistics.mean(signed) if signed else None,
            "worst_decile_mean_positive_loss": statistics.mean(tail) if tail else None,
        },
        "end_to_end_ms": distribution([r.get("total_ms") for _, r in runs]),
        "cpu_ms": distribution([r.get("child_cpu_ms") for _, r in runs]),
        "peak_rss_bytes": distribution([r.get("peak_rss_bytes") for _, r in runs]),
        "startup_transport_ms": distribution([r.get("startup_and_transport_ms") for _, r in runs]),
        "stages_ms": {
            stage: distribution([r.get("timings", {}).get(stage) for _, r in runs])
            for stage in (
                "startup_import_ms",
                "greedy_ms",
                "feature_ms",
                "model_build_ms",
                "native_solve_ms",
                "validation_ms",
            )
        },
    }


def analyze(rows):
    policies = ("greedy", "cp_sat", "warm_cp_sat")

    def summarize(group):
        return {"groups": len(group), "policies": {p: summarize_policy(group, p) for p in policies}}

    return {
        "overall": summarize(rows),
        "by_split": {
            key: summarize([row for row in rows if row["split"] == key])
            for key in sorted({row["split"] for row in rows})
        },
        "by_family": {
            key: summarize([row for row in rows if row["family"] == key])
            for key in sorted({row["family"] for row in rows})
        },
        "by_task_count": {
            str(key): summarize([row for row in rows if row["parameters"]["task_count"] == key])
            for key in sorted({row["parameters"]["task_count"] for row in rows})
        },
        "reference_proofs": dict(
            Counter(row["reference"].get("proof") or "NO_OPTIMALITY_PROOF" for row in rows)
        ),
        "limits": (
            "Repeated runs are correlated. Quality means include only paired "
            "valid outcomes; all missing/invalid counts remain explicit. "
            "CPU/RSS absent for killed children is unknown, never zero. This "
            "report does not promote a routing model."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-final",
        action="store_true",
        help="Only after the routing configuration is frozen",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output exists; preserve original evidence and choose a new filename")
    if args.input.is_dir():
        paths = sorted(args.input.glob("[0-9]*.json"))
        if not args.include_final:
            paths = [path for path in paths if int(path.stem) < 800]
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    else:
        rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines()]
        rows = [row for row in rows if args.include_final or row["split"] != "test"]
    result = analyze(rows)
    result["includes_final"] = args.include_final
    result["source"] = str(args.input)
    if args.input.is_file():
        result["source_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"groups": len(rows), "output": str(args.output), "includes_final": args.include_final}
        )
    )


if __name__ == "__main__":
    main()
