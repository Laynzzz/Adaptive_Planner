"""Audited arithmetic correction; preserve the original report and frozen choices.

This does not refit, reselect, remeasure or repeat classifier inference. Only the
cold baseline's raw-name mapping and dependent comparisons are recomputed.
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from training.evaluate import (
    _pairs,
    _promotion,
    _read_artifact,
    paired_bootstrap,
    score_policy,
    summarize_records,
)


def correct(original_path, selection_path, output_path):
    original_path, selection_path, output_path = map(
        Path, (original_path, selection_path, output_path)
    )
    original_bytes = original_path.read_bytes()
    report = json.loads(original_bytes)
    selection_bytes = selection_path.read_bytes()
    selection = json.loads(selection_bytes)
    if report["selection_sha256"] != hashlib.sha256(selection_bytes).hexdigest():
        raise ValueError("SELECTION_HASH_MISMATCH")
    if report["test_sha256"] != selection["artifacts"]["test"]["sha256"]:
        raise ValueError("TEST_HASH_MISMATCH")
    old = report["policies"]["cold_cp_sat"]
    if old["missing_result_count"] != old["attempt_count"]:
        raise ValueError("CORRECTION_NOT_APPLICABLE")
    rows = _read_artifact(selection["artifacts"]["test"], "test")
    if not all(any(r["policy"] == "cp_sat" for r in row["policy_results"]) for row in rows):
        raise ValueError("EXPECTED_RAW_ALIAS_MISSING")
    cold = score_policy(rows, "cold_cp_sat")
    report["policies"]["cold_cp_sat"] = cold
    report["per_family"]["cold_cp_sat"] = {
        family: {
            key: value
            for key, value in summarize_records(
                [r for r in cold["records"] if r["family"] == family]
            ).items()
            if key != "records"
        }
        for family in sorted({r["family"] for r in cold["records"]})
    }
    selected = report["policies"]["learned"]
    pairs, completion = _pairs(selected, cold)
    report["uncertainty"]["cold_cp_sat"] = paired_bootstrap(
        pairs, seed=report["seed"], samples=report["bootstrap_samples"]
    )
    report["completion_losses_vs_baselines"]["cold_cp_sat"] = completion
    metrics, decision = _promotion(
        selected,
        report["policies"]["simple_router"],
        cold,
        report["uncertainty"]["simple_router"],
    )
    report["promotion_metrics"] = metrics
    report["decision"] = asdict(decision)
    # Preserve every preexisting veto unrelated to the missing cold baseline.
    retained = [
        gate
        for gate in json.loads(original_bytes)["decision"]["failed_gates"]
        if gate != "INSUFFICIENT_PAIRED_EVIDENCE"
    ]
    report["decision"]["failed_gates"] = list(dict.fromkeys([*decision.failed_gates, *retained]))
    report["decision"]["promote"] = not report["decision"]["failed_gates"]
    report["correction"] = {
        "reason": "Raw cp_sat is the cold_cp_sat baseline, previously counted as missing",
        "original_report_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "original_report": str(original_path),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Cold baseline records and dependent statistics only; all other records unchanged",
        "selection_changed": False,
        "classifier_inference_repeated": False,
        "original_report_and_marker_preserved": True,
    }
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report["decision"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(correct(args.original, args.selection, args.output)))


if __name__ == "__main__":
    main()
