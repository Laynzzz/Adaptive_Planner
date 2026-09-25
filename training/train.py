"""Train on known training labels; freeze model and threshold using validation only."""

import argparse
import hashlib
import itertools
import json
import platform
from importlib.metadata import version
from pathlib import Path

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from planner.ml.features import FEATURE_NAMES, FeatureVector
from training.artifacts import export_pipeline

SEED = 20260925
THRESHOLDS = (0.1, 0.25, 0.5, 0.75, 0.9)


def vector(features):
    return FeatureVector(FEATURE_NAMES, tuple(features[name] for name in FEATURE_NAMES))


def validate_splits(train, validation):
    if any(row["split"] != "train" for row in train):
        raise ValueError("TRAIN_ONLY")
    if any(row["split"] != "validation" for row in validation):
        raise ValueError("VALIDATION_ONLY")
    groups = [row["group_id"] for row in train + validation]
    if len(groups) != len(set(groups)):
        raise ValueError("GROUP_LEAKAGE")


def fit_candidates(rows, seed=SEED):
    if any(row["split"] != "train" for row in rows):
        raise ValueError("TRAIN_ONLY")
    labeled = [row for row in rows if isinstance(row.get("label"), bool) and row.get("features")]
    y = [int(row["label"]) for row in labeled]
    if set(y) != {0, 1}:
        raise ValueError("INSUFFICIENT_TRAIN_LABELS")
    x = [vector(row["features"]).values for row in labeled]
    models = {
        "logistic": LogisticRegression(C=1, max_iter=1000, random_state=seed),
        "gradient_boosted": GradientBoostingClassifier(
            n_estimators=50, max_depth=2, learning_rate=0.1, random_state=seed
        ),
    }
    return {
        name: export_pipeline(make_pipeline(StandardScaler(), model).fit(x, y))
        for name, model in models.items()
    }


def simple_decision(features, rule):
    return (
        features["utilization"] >= rule["utilization"]
        or features["slack_min"] <= rule["slack_min"]
        or features["greedy_quality"] < rule["greedy_quality"]
    )


def rank(summary):
    """Safety/quality constraints first, latency among eligible validation candidates."""
    loss = summary["mean_quality_loss"]
    tail = summary["worst_decile_quality_loss"]
    failures = summary["reference_completion_losses"]
    latency = summary["mean_total_ms"]
    if loss is None or tail is None or latency is None or summary.get("missing_latency_count", 0):
        return (True, failures, float("inf"), float("inf"))
    eligible = failures == 0 and loss <= 0.02 and tail <= 0.05
    return (not eligible, failures, 0 if eligible else loss, latency)


def read_split(artifact):
    path = Path(artifact["path"])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
        raise ValueError("DATASET_HASH_MISMATCH")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def freeze_selection(dataset_manifest, output_dir):
    from training.evaluate import score_policy

    def summarize(chooser):
        summary = score_policy(validation, chooser)
        summary.pop("records", None)
        return summary

    dataset = json.loads(dataset_manifest.read_text(encoding="utf-8"))
    if dataset.get("partial"):
        raise ValueError("PARTIAL_DATASET_NOT_RELEASE")
    train = read_split(dataset["artifacts"]["train"])
    validation = read_split(dataset["artifacts"]["validation"])
    validate_splits(train, validation)
    if not train or not validation:
        raise ValueError("EMPTY_SELECTION_SPLIT")
    if output_dir.exists():
        raise ValueError("OUTPUT_EXISTS_CHOOSE_NEW_EXPERIMENT")
    output_dir.mkdir(parents=True)
    trials = []
    for utilization, slack, quality in itertools.product(
        (0.5, 0.75, 1.0), (0.0, 0.1, 0.25), (0.5, 0.75, 0.9)
    ):
        rule = {"utilization": utilization, "slack_min": slack, "greedy_quality": quality}
        summary = summarize(lambda features, rule=rule: simple_decision(features, rule))
        trials.append({"rule": rule, "summary": summary})
    simple = min(trials, key=lambda trial: rank(trial["summary"]))
    result = {
        "version": "routing-selection-v1",
        "seed": SEED,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "scikit_learn": version("scikit-learn"),
            "numpy": version("numpy"),
            "ortools": version("ortools"),
        },
        "objective_version": "v1",
        "training_configuration": {
            "preprocessing": "StandardScaler fit only on known labeled training rows",
            "logistic": {"C": 1, "max_iter": 1000, "random_state": SEED},
            "gradient_boosted": {
                "n_estimators": 50,
                "max_depth": 2,
                "learning_rate": 0.1,
                "random_state": SEED,
            },
            "thresholds": THRESHOLDS,
        },
        "code_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                Path(__file__),
                Path("training/evaluate.py"),
                Path("training/artifacts.py"),
                Path("training/promote.py"),
                Path("services/planner/src/planner/ml/features.py"),
                Path("services/planner/src/planner/ml/manifest.py"),
                Path("services/planner/src/planner/ml/router.py"),
            ]
        },
        "dataset_manifest_sha256": hashlib.sha256(dataset_manifest.read_bytes()).hexdigest(),
        "measurement_limitations": dataset.get("measurement_limitations", []),
        "artifacts": dataset["artifacts"],
        "simple_rule": simple["rule"],
        "simple_validation": simple["summary"],
        "cp_budget_ms": 200,
        "wall_budget_ms": 2000,
        "selection_criterion": (
            "Completion and quality constraints first; "
            "minimum validation mean total latency among eligible candidates"
        ),
        "train_groups": len(train),
        "validation_groups": len(validation),
        "known_train_labels": sum(isinstance(row.get("label"), bool) for row in train),
        "test_access": "Test path and hash copied without opening test rows",
    }
    try:
        models = fit_candidates(train)
    except ValueError as error:
        if str(error) != "INSUFFICIENT_TRAIN_LABELS":
            raise
        result.update(
            status="INSUFFICIENT_TRAIN_LABELS", model_path=None, model_sha256=None, threshold=None
        )
    else:
        model_trials = []
        for name, model in models.items():
            path = output_dir / f"{name}.json"
            path.write_text(model.model_dump_json() + "\n", encoding="utf-8", newline="\n")
            for threshold in THRESHOLDS:
                summary = summarize(
                    lambda features, model=model, threshold=threshold: (
                        model.probability(vector(features)) >= threshold
                    ),
                )
                model_trials.append({"model": name, "threshold": threshold, "summary": summary})
        chosen = min(model_trials, key=lambda trial: rank(trial["summary"]))
        result["candidate_models"] = {}
        for name in models:
            candidate = min(
                (trial for trial in model_trials if trial["model"] == name),
                key=lambda trial: rank(trial["summary"]),
            )
            candidate_path = output_dir / f"{name}.json"
            result["candidate_models"][name] = {
                "model_path": candidate_path.name,
                "model_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
                "threshold": candidate["threshold"],
            }
        path = output_dir / f"{chosen['model']}.json"
        result.update(
            status="SELECTED",
            model_path=path.name,
            model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            threshold=chosen["threshold"],
            selected_model=chosen["model"],
            selected_validation=chosen["summary"],
            candidates=model_trials,
        )
    result["simple_trials"] = trials
    path = output_dir / "selection.json"
    path.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(freeze_selection(args.dataset_manifest, args.output_dir))


if __name__ == "__main__":
    main()
