"""Evaluate frozen routing choices; grouped uncertainty never selects on test.

Policy replay uses measured greedy/cold/warm outcomes, with chooser overhead added
to the selected path. It is an observational replay, not a new end-to-end load test.
Unknown supervised labels and failed attempts remain in policy denominators.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from math import ceil, isfinite, log
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter

from planner.ml.features import FEATURE_NAMES, FeatureVector
from planner.ml.manifest import load_artifact
from training.promote import PromotionDecision, PromotionMetrics, evaluate_promotion

POLICIES = ("greedy", "cold_cp_sat", "warm_cp_sat", "reference")


def quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _valid(result):
    return bool(
        result.get("validated")
        and not result.get("invalid")
        and result.get("status") in ("FEASIBLE", "OPTIMAL")
        and _finite(result.get("quality"))
        and 0 <= result["quality"] <= 1
    )


def _features(row, greedy):
    values = greedy.get("features") or row.get("features")
    if not isinstance(values, dict) or set(values) != set(FEATURE_NAMES):
        return None
    try:
        FeatureVector(FEATURE_NAMES, tuple(values[name] for name in FEATURE_NAMES))
    except (ValueError, TypeError):
        return None
    return {name: values[name] for name in FEATURE_NAMES}


def summarize_records(records):
    losses = [r["positive_quality_loss"] for r in records if r["positive_quality_loss"] is not None]
    signed = [
        r["signed_quality_difference"]
        for r in records
        if r["signed_quality_difference"] is not None
    ]
    latencies = [r["total_ms"] for r in records if r["total_ms"] is not None]
    cpu = [r["cpu_ms"] for r in records if r["cpu_ms"] is not None]
    groups = {r["group_id"] for r in records}
    unknown_groups = {r["group_id"] for r in records if r["label_unknown"]}
    known = [r for r in records if r["known_feasible"]]
    tail = sorted(losses, reverse=True)[: max(1, ceil(len(losses) * 0.1))]
    return dict(
        scenario_count=len({r["scenario_id"] for r in records}),
        group_count=len(groups),
        attempt_count=len(records),
        completed_count=sum(r["completed"] for r in records),
        paired_valid_count=len(losses),
        invalid_accepted=sum(r["invalid_accepted"] for r in records),
        invalid_result_count=sum(r["invalid_result"] for r in records),
        missing_result_count=sum(r["status"] == "MISSING" for r in records),
        missing_latency_count=len(records) - len(latencies),
        missing_cpu_count=len(records) - len(cpu),
        unknown_label_count=len(unknown_groups),
        status_counts=dict(sorted(Counter(r["status"] for r in records).items())),
        known_feasible_attempt_count=len(known),
        known_feasible_completed_count=sum(r["completed"] for r in known),
        reference_completion_losses=sum(r["reference_completion_loss"] for r in records),
        mean_quality_loss=mean(losses) if losses else None,
        worst_decile_quality_loss=mean(tail) if tail else None,
        signed_quality_difference=mean(signed) if signed else None,
        mean_total_ms=mean(latencies) if latencies else None,
        p50_total_ms=quantile(latencies, 0.5),
        p95_total_ms=quantile(latencies, 0.95),
        mean_cpu_ms=mean(cpu) if cpu else None,
        escalation_rate=sum(r["selected_policy"] in ("cold_cp_sat", "warm_cp_sat") for r in records)
        / max(1, len(records)),
        mean_inference_ms=mean(r["inference_ms"] for r in records) if records else 0,
        records=records,
    )


def score_policy(rows, chooser, *, artifact_load_ms=0.0):
    """chooser(features)->bool escalates to warm CP; fixed string selects a baseline.

    Completion loss counts known-feasible attempts where any measured reference or
    baseline supplied a valid schedule. Missing results are never successful and
    missing latency is null, never an imputed zero.
    """
    if isinstance(chooser, str) and chooser not in POLICIES:
        raise ValueError("UNKNOWN_POLICY")
    if not _finite(artifact_load_ms) or artifact_load_ms < 0:
        raise ValueError("INVALID_ARTIFACT_LOAD_TIME")
    records = []
    for row in rows:
        observed = row["policy_results"]
        repeats = sorted({r.get("repeat", 0) for r in observed}) or [0]
        if len(repeats) > 10:
            raise ValueError("POLICY_REPEAT_LIMIT")
        if chooser == "reference":
            repeats = [0]
        best = row["reference"]
        reference_quality = best["quality"] if _valid(best) else None
        reference_success = any(_valid(r) for r in [best, *observed])
        for repeat in repeats:
            by_policy = {}
            for result in observed:
                if result.get("repeat", 0) == repeat:
                    policy = "cold_cp_sat" if result["policy"] == "cp_sat" else result["policy"]
                    if policy in by_policy:
                        raise ValueError("DUPLICATE_POLICY_REPEAT")
                    by_policy[policy] = result
            greedy = by_policy.get("greedy", {})
            inference_ms = 0.0
            if isinstance(chooser, str):
                selected = chooser
            else:
                features = _features(row, greedy)
                if not _valid(greedy) or features is None:
                    selected = "warm_cp_sat"
                else:
                    start = perf_counter()
                    escalate = chooser(features)
                    inference_ms = (perf_counter() - start) * 1000 + artifact_load_ms
                    if not isinstance(escalate, bool):
                        raise ValueError("ROUTER_MUST_RETURN_BOOLEAN")
                    selected = "warm_cp_sat" if escalate else "greedy"
            result = (
                best.get("requested_reference", best)
                if selected == "reference"
                else by_policy.get(selected, {})
            )
            valid = _valid(result)
            quality = result.get("quality") if valid else None
            delta = (
                quality - reference_quality
                if quality is not None and reference_quality is not None
                else None
            )
            elapsed = result.get("total_ms")
            cpu = result.get("child_cpu_ms")
            records.append(
                dict(
                    scenario_id=row["scenario_id"],
                    group_id=row["group_id"],
                    family=row["family"],
                    repeat=repeat,
                    selected_policy=selected,
                    status=result.get("status", "MISSING"),
                    completed=valid,
                    quality=quality,
                    known_feasible=bool(row["known_feasible"]),
                    label_unknown=row.get("label") is None,
                    invalid_accepted=bool(result.get("validated") and result.get("invalid")),
                    invalid_result=bool(
                        result.get("invalid") or result.get("status") == "MODEL_INVALID"
                    ),
                    positive_quality_loss=max(0.0, -delta) if delta is not None else None,
                    signed_quality_difference=delta,
                    reference_completion_loss=bool(
                        row["known_feasible"] and reference_success and not valid
                    ),
                    total_ms=elapsed + inference_ms if _finite(elapsed) and elapsed >= 0 else None,
                    cpu_ms=cpu if _finite(cpu) and cpu >= 0 else None,
                    inference_ms=inference_ms,
                )
            )
    return summarize_records(records)


def paired_bootstrap(pairs, *, seed=20260925, samples=2000):
    """Resample base groups, retaining all variants and repeated measurements together."""
    if not 1 <= samples <= 10000:
        raise ValueError("BOOTSTRAP_SAMPLE_LIMIT")
    if len(pairs) * samples > 20_000_000:
        raise ValueError("BOOTSTRAP_WORK_LIMIT")
    grouped = defaultdict(list)
    missing = 0
    for pair in pairs:
        if not all(_finite(pair.get(k)) and pair[k] >= 0 for k in ("baseline_ms", "policy_ms")):
            missing += 1
            continue
        grouped[pair["group_id"]].append(pair)
    keys = sorted(grouped)
    if not keys:
        return dict(
            group_count=0,
            paired_count=0,
            missing_pairs=missing,
            mean_improvement_ci_ms=None,
            p95_gain_ci=None,
            samples=samples,
            seed=seed,
        )
    random = Random(seed)
    improvements, gains = [], []
    for _ in range(samples):
        selected = [pair for _ in keys for pair in grouped[random.choice(keys)]]
        improvements.append(mean(p["baseline_ms"] - p["policy_ms"] for p in selected))
        baseline95 = quantile([p["baseline_ms"] for p in selected], 0.95)
        policy95 = quantile([p["policy_ms"] for p in selected], 0.95)
        if baseline95 > 0:
            gains.append((baseline95 - policy95) / baseline95)
    return dict(
        group_count=len(keys),
        paired_count=sum(map(len, grouped.values())),
        missing_pairs=missing,
        mean_improvement_ci_ms=[quantile(improvements, 0.025), quantile(improvements, 0.975)],
        p95_gain_ci=[quantile(gains, 0.025), quantile(gains, 0.975)] if gains else None,
        samples=samples,
        seed=seed,
    )


def _simple(features, rule):
    return bool(
        features["utilization"] >= rule["utilization"]
        or features["slack_min"] <= rule["slack_min"]
        or features["greedy_quality"] < rule["greedy_quality"]
    )


def _classification(rows, model, threshold):
    known = [row for row in rows if isinstance(row.get("label"), bool)]
    observations = []
    for row in known:
        features = _features(row, row["greedy"])
        if features is not None:
            probability = model.probability(FeatureVector(FEATURE_NAMES, tuple(features.values())))
            observations.append((int(row["label"]), probability))
    confusion = dict(true_positive=0, true_negative=0, false_positive=0, false_negative=0)
    for truth, probability in observations:
        prediction = probability >= threshold
        confusion[
            ("true_" if prediction == bool(truth) else "false_")
            + ("positive" if prediction else "negative")
        ] += 1
    bins = []
    for index in range(10):
        bucket = [(y, p) for y, p in observations if min(9, int(p * 10)) == index]
        bins.append(
            dict(
                lower=index / 10,
                upper=(index + 1) / 10,
                count=len(bucket),
                mean_probability=mean(p for _, p in bucket) if bucket else None,
                positive_fraction=mean(y for y, _ in bucket) if bucket else None,
            )
        )
    return dict(
        labeled_count=len(known),
        scored_labeled_count=len(observations),
        unknown_label_count=len(rows) - len(known),
        missing_features_count=len(known) - len(observations),
        label_reason_counts=dict(
            sorted(Counter(row.get("label_reason", "UNSPECIFIED") for row in rows).items())
        ),
        threshold=threshold,
        confusion=confusion,
        accuracy=(confusion["true_positive"] + confusion["true_negative"]) / len(observations)
        if observations
        else None,
        brier_score=mean((p - y) ** 2 for y, p in observations) if observations else None,
        log_loss=mean(
            -y * log(max(1e-15, p)) - (1 - y) * log(max(1e-15, 1 - p)) for y, p in observations
        )
        if observations
        else None,
        calibration_bins=bins,
    )


def _pairs(policy, baseline):
    observed = {(r["scenario_id"], r["repeat"]): r for r in baseline["records"]}
    pairs = []
    completion_losses = 0
    for chosen in policy["records"]:
        other = observed.get((chosen["scenario_id"], chosen["repeat"]))
        if other is None:
            raise ValueError("UNPAIRED_POLICY_EXECUTION")
        completion_losses += bool(other["completed"] and not chosen["completed"])
        pairs.append(
            dict(
                group_id=chosen["group_id"],
                baseline_ms=other["total_ms"],
                policy_ms=chosen["total_ms"],
            )
        )
    return pairs, completion_losses


def _read_artifact(spec, expected_split, *, group_only=False):
    path = Path(spec["path"])
    if path.stat().st_size > 1_000_000_000:
        raise ValueError("DATASET_ARTIFACT_TOO_LARGE")
    digest = hashlib.sha256()
    rows = []
    with path.open("rb") as stream:
        while line := stream.readline(10_000_001):
            if len(line) > 10_000_000 or len(rows) >= 1000:
                raise ValueError("DATASET_ROW_LIMIT")
            digest.update(line)
            if line.strip():
                row = json.loads(line)
                if (
                    row.get("split") != expected_split
                    or row.get("schema_version") != "routing-dataset-v1"
                ):
                    raise ValueError("DATASET_SPLIT_OR_SCHEMA_MISMATCH")
                rows.append({"group_id": row["group_id"]} if group_only else row)
    if digest.hexdigest() != spec["sha256"]:
        raise ValueError("DATASET_HASH_MISMATCH")
    if len({r["group_id"] for r in rows}) != spec.get("groups", len(rows)):
        raise ValueError("DATASET_GROUP_COUNT_MISMATCH")
    return rows


def _model_bundle(spec, trusted_root):
    threshold = spec.get("threshold")
    if not _finite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("INVALID_FROZEN_THRESHOLD")
    started = perf_counter()
    model = load_artifact(trusted_root / spec["model_path"], spec["model_sha256"], trusted_root)
    elapsed = (perf_counter() - started) * 1000
    return model, threshold, elapsed


def _promotion(selected, simple, cold, uncertainty):
    _, simple_losses = _pairs(selected, simple)
    needed = [
        selected["mean_quality_loss"],
        selected["worst_decile_quality_loss"],
        selected["p95_total_ms"],
        simple["p95_total_ms"],
        cold["p95_total_ms"],
        simple["mean_quality_loss"],
        uncertainty["mean_improvement_ci_ms"],
    ]
    if (
        any(value is None for value in needed)
        or simple["p95_total_ms"] <= 0
        or cold["p95_total_ms"] <= 0
    ):
        return None, PromotionDecision(False, ("INSUFFICIENT_PAIRED_EVIDENCE",))
    metrics = PromotionMetrics(
        test_count=selected["attempt_count"],
        paired_valid_count=selected["paired_valid_count"],
        invalid_accepted=selected["invalid_accepted"],
        reference_completion_losses=selected["reference_completion_losses"],
        simple_completion_losses=simple_losses,
        mean_quality_loss=selected["mean_quality_loss"],
        worst_decile_quality_loss=selected["worst_decile_quality_loss"],
        always_solver_p95_gain=1 - selected["p95_total_ms"] / cold["p95_total_ms"],
        simple_router_p95_gain=1 - selected["p95_total_ms"] / simple["p95_total_ms"],
        simple_router_mean_loss_difference=selected["mean_quality_loss"]
        - simple["mean_quality_loss"],
        paired_latency_improvement_ci=tuple(uncertainty["mean_improvement_ci_ms"]),
    )
    decision = evaluate_promotion(metrics)
    if any(s["missing_latency_count"] for s in (selected, simple, cold)):
        decision = PromotionDecision(False, (*decision.failed_gates, "MISSING_LATENCY"))
    return asdict(metrics), decision


def evaluate_frozen(selection_path, output_path, *, bootstrap_samples=2000, allow_partial=False):
    """Read untouched test only after validating and recording a frozen selection hash.

    An exclusive marker prevents accidental second evaluation/tuning in the same
    experiment directory. Unit tests use entirely synthetic temporary artifacts.
    """
    selection_path, output_path = Path(selection_path), Path(output_path)
    if output_path.exists():
        raise ValueError("EVALUATION_OUTPUT_EXISTS")
    if selection_path.stat().st_size > 100_000_000:
        raise ValueError("SELECTION_TOO_LARGE")
    raw_selection = selection_path.read_bytes()
    selection = json.loads(raw_selection)
    if selection.get("version") != "routing-selection-v1" or selection.get("status") not in (
        "SELECTED",
        "INSUFFICIENT_TRAIN_LABELS",
    ):
        raise ValueError("SELECTION_NOT_FROZEN")
    if not 1 <= bootstrap_samples <= 10000:
        raise ValueError("BOOTSTRAP_SAMPLE_LIMIT")
    rule = selection["simple_rule"]
    if set(rule) != {"utilization", "slack_min", "greedy_quality"} or not all(
        _finite(v) for v in rule.values()
    ):
        raise ValueError("INVALID_FROZEN_SIMPLE_RULE")
    seed = selection["seed"]
    bundles = {}
    if selection["status"] == "SELECTED":
        bundles["learned"] = _model_bundle(selection, selection_path.parent)
        for name, spec in selection.get("candidate_models", {}).items():
            bundles[name] = _model_bundle(spec, selection_path.parent)
    # Train/validation IDs may be inspected before the freeze; outcomes are not used here.
    train = _read_artifact(selection["artifacts"]["train"], "train", group_only=True)
    validation = _read_artifact(selection["artifacts"]["validation"], "validation", group_only=True)
    train_groups, validation_groups = (
        {r["group_id"] for r in train},
        {r["group_id"] for r in validation},
    )
    if train_groups & validation_groups:
        raise ValueError("GROUP_LEAKAGE")
    if not allow_partial and (
        len(train_groups),
        len(validation_groups),
        selection["artifacts"]["test"].get("groups"),
    ) != (600, 200, 200):
        raise ValueError("FINAL_SPLIT_SIZE_MISMATCH")
    selection_hash = hashlib.sha256(raw_selection).hexdigest()
    marker = selection_path.with_name("test-evaluation.started.json")
    with marker.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            dict(
                selection_sha256=selection_hash,
                test_sha256=selection["artifacts"]["test"]["sha256"],
                started_at=datetime.now(UTC).isoformat(),
            ),
            stream,
        )
    test = _read_artifact(selection["artifacts"]["test"], "test")
    test_groups = {r["group_id"] for r in test}
    if test_groups & (train_groups | validation_groups):
        raise ValueError("GROUP_LEAKAGE")
    if not test or len({r["scenario_id"] for r in test}) != len(test):
        raise ValueError("EMPTY_OR_DUPLICATE_TEST_SCENARIOS")
    summaries = {name: score_policy(test, name) for name in POLICIES}
    summaries["simple_router"] = score_policy(test, lambda features: _simple(features, rule))
    classifications = {}
    for name, (model, threshold, load_ms) in bundles.items():
        summaries[name] = score_policy(
            test,
            lambda features, model=model, threshold=threshold: bool(
                model.probability(FeatureVector(FEATURE_NAMES, tuple(features.values())))
                >= threshold
            ),
            artifact_load_ms=load_ms,
        )
        classifications[name] = _classification(test, model, threshold)
    uncertainty, completion_comparisons = {}, {}
    metrics, decision = None, PromotionDecision(False, ("INSUFFICIENT_TRAIN_LABELS",))
    if "learned" in summaries:
        selected = summaries["learned"]
        for baseline in ("simple_router", "cold_cp_sat", "warm_cp_sat", "greedy"):
            pairs, completion = _pairs(selected, summaries[baseline])
            uncertainty[baseline] = paired_bootstrap(pairs, seed=seed, samples=bootstrap_samples)
            completion_comparisons[baseline] = completion
        metrics, decision = _promotion(
            selected,
            summaries["simple_router"],
            summaries["cold_cp_sat"],
            uncertainty["simple_router"],
        )
    if allow_partial:
        decision = PromotionDecision(
            False, (*decision.failed_gates, "PARTIAL_DEVELOPMENT_EVALUATION")
        )
    if selection.get("measurement_limitations"):
        decision = PromotionDecision(
            False, (*decision.failed_gates, "MEASUREMENT_SUPERVISION_LIMIT")
        )
    families = {}
    for name, summary in summaries.items():
        families[name] = {
            family: {
                key: value
                for key, value in summarize_records(
                    [r for r in summary["records"] if r["family"] == family]
                ).items()
                if key != "records"
            }
            for family in sorted({r["family"] for r in summary["records"]})
        }
    report = dict(
        version="routing-evaluation-v1",
        selection_sha256=selection_hash,
        test_sha256=selection["artifacts"]["test"]["sha256"],
        base_group_count=len(test_groups),
        scenario_count=len(test),
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        policies=summaries,
        per_family=families,
        classification=classifications,
        uncertainty=uncertainty,
        completion_losses_vs_baselines=completion_comparisons,
        promotion_metrics=metrics,
        decision=asdict(decision),
        timing_method=(
            "Observed policy replay; chosen warm path includes greedy/features/startup "
            "once. Measured inference and one artifact load per model decision are added. "
            "No fresh routed subprocess executions."
        ),
        load_ms_by_model={name: bundle[2] for name, bundle in bundles.items()},
        reference_method=(
            "Best validated measured reference/baseline quality; completion loss on "
            "known-feasible attempts against any measured valid schedule. Reference execution "
            "timing is requested_reference once per scenario."
        ),
        bootstrap_method=(
            "Paired base-group resampling retains variants/repeats together; 95% "
            "percentile intervals. p95 uncertainty is separate from paired mean improvement."
        ),
        missing_method=(
            "Null quality/latency retained with explicit counts; no successful-result "
            "or zero-latency imputation. Unknown training labels remain in every policy evaluation."
        ),
        test_selection="No model, rule or threshold selection was performed using test outcomes.",
        measurement_limitations=selection.get("measurement_limitations", []),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_bytes = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    with output_path.open("xb") as stream:
        stream.write(output_bytes)
    release_path = output_path.with_name("finalrelease.json")
    # Keep the release and artifact under the same trusted experiment root.
    model_path = None
    if selection.get("model_path"):
        import os

        model_path = os.path.relpath(
            (selection_path.parent / selection["model_path"]).resolve(),
            output_path.parent.resolve(),
        )
    release = dict(
        version="routing-release-v1",
        promote=decision.promote,
        model_path=model_path,
        model_sha256=selection.get("model_sha256"),
        threshold=selection.get("threshold"),
        cp_budget_ms=selection["cp_budget_ms"],
        selection_sha256=selection_hash,
        evaluation_sha256=hashlib.sha256(output_bytes).hexdigest(),
    )
    with release_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(release, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Frozen selection.json, never a tunable dataset manifest",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Synthetic development only; permanently denies promotion",
    )
    args = parser.parse_args()
    output = args.output or args.manifest.with_name("test-evaluation.json")
    report = evaluate_frozen(
        args.manifest,
        output,
        bootstrap_samples=args.bootstrap_samples,
        allow_partial=args.allow_partial,
    )
    print(
        json.dumps(
            dict(
                output=str(output),
                decision=report["decision"],
                base_groups=report["base_group_count"],
            )
        )
    )


if __name__ == "__main__":
    main()
