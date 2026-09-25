"""Synthetic rows test evaluation arithmetic without opening any held-out data."""

import pytest

from planner.ml.features import FEATURE_NAMES


def row(group="base-a", *, greedy_valid=True, label=None, repeats=1):
    features = dict.fromkeys(FEATURE_NAMES, 0.0)
    features.update(greedy_valid=float(greedy_valid), greedy_quality=0.9)
    results = []
    for repeat in range(repeats):
        for name, quality, elapsed in [
            ("greedy", 0.9, 10),
            ("cold_cp_sat", 1.0, 110),
            ("warm_cp_sat", 1.0, 120),
        ]:
            valid = greedy_valid if name == "greedy" else True
            results.append(
                dict(
                    policy=name,
                    repeat=repeat,
                    validated=valid,
                    invalid=False,
                    status="FEASIBLE" if valid else "UNKNOWN",
                    quality=quality if valid else None,
                    total_ms=elapsed,
                    child_cpu_ms=elapsed / 2,
                )
            )
    reference = dict(validated=True, invalid=False, quality=1.0, status="OPTIMAL", total_ms=200)
    return dict(
        schema_version="routing-dataset-v1",
        scenario_id=group,
        group_id=group,
        split="test",
        family="synthetic",
        known_feasible=True,
        features=features,
        reference=reference,
        greedy=results[0],
        policy_results=results,
        label=label,
        label_reason="REFERENCE_SEARCH_CENSORED" if label is None else "PROVEN_LABEL",
    )


def test_policy_metrics_retain_unknown_labels_and_failed_attempts():
    from training.evaluate import score_policy

    a, b = row("a", repeats=2), row("b", greedy_valid=False, repeats=2)
    summary = score_policy([a, b], "greedy")
    assert summary["attempt_count"] == 4
    assert summary["unknown_label_count"] == 2
    assert summary["completed_count"] == 2
    assert summary["reference_completion_losses"] == 2
    assert summary["mean_quality_loss"] == pytest.approx(0.1)
    assert summary["signed_quality_difference"] == pytest.approx(-0.1)
    assert summary["p95_total_ms"] == 10
    assert len(summary["records"]) == 4


def test_invalid_greedy_bypasses_model_and_warm_latency_is_not_double_counted():
    from training.evaluate import score_policy

    def should_not_call(_):
        raise AssertionError("Invalid greedy must bypass classifier.")

    summary = score_policy([row(greedy_valid=False)], should_not_call)
    assert summary["escalation_rate"] == 1
    assert summary["mean_total_ms"] == 120
    assert summary["mean_quality_loss"] == 0


def test_missing_result_and_latency_remain_explicit_not_zero():
    from training.evaluate import score_policy

    data = row()
    data["policy_results"] = [r for r in data["policy_results"] if r["policy"] != "cold_cp_sat"]
    summary = score_policy([data], "cold_cp_sat")
    assert summary["attempt_count"] == 1
    assert summary["missing_result_count"] == 1
    assert summary["missing_latency_count"] == 1
    assert summary["mean_total_ms"] is None
    assert summary["mean_quality_loss"] is None
    assert summary["reference_completion_losses"] == 1


def test_grouped_bootstrap_does_not_treat_repeats_as_independent_cases():
    from training.evaluate import paired_bootstrap

    pairs = [{"group_id": "a", "baseline_ms": 100.0, "policy_ms": 50.0}] * 100
    pairs += [{"group_id": "b", "baseline_ms": 100.0, "policy_ms": 150.0}] * 100
    result = paired_bootstrap(pairs, seed=7, samples=500)
    assert result["group_count"] == 2
    assert result["mean_improvement_ci_ms"] == [-50.0, 50.0]
    assert result == paired_bootstrap(pairs, seed=7, samples=500)


def test_model_is_never_given_future_cp_outcome_features():
    from training.evaluate import score_policy

    observed = []

    def chooser(features):
        observed.append(features)
        assert set(features) == set(FEATURE_NAMES)
        return False

    result = score_policy([row()], chooser)
    assert observed
    assert result["records"][0]["selected_policy"] == "greedy"
    assert result["mean_total_ms"] >= 10


def synthetic_frozen_selection(tmp_path):
    import hashlib
    import json

    artifacts = {}
    for split in ("train", "validation", "test"):
        data = row(split)
        data["split"] = split
        path = tmp_path / f"{split}.jsonl"
        path.write_text(json.dumps(data) + "\n", encoding="utf-8")
        artifacts[split] = dict(
            path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), groups=1
        )
    selection = dict(
        version="routing-selection-v1",
        status="INSUFFICIENT_TRAIN_LABELS",
        seed=7,
        artifacts=artifacts,
        simple_rule={"utilization": 1.0, "slack_min": -1.0, "greedy_quality": 0.5},
        model_path=None,
        model_sha256=None,
        threshold=None,
        cp_budget_ms=200,
        wall_budget_ms=2000,
    )
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(selection), encoding="utf-8")
    return path


def test_frozen_evaluation_records_test_access_once_and_denies_partial_promotion(tmp_path):
    import json

    from training.evaluate import evaluate_frozen

    selection = synthetic_frozen_selection(tmp_path)
    result = evaluate_frozen(
        selection, tmp_path / "report.json", bootstrap_samples=10, allow_partial=True
    )
    assert result["base_group_count"] == 1
    assert result["policies"]["greedy"]["unknown_label_count"] == 1
    assert result["decision"]["promote"] is False
    assert (tmp_path / "test-evaluation.started.json").exists()
    release = json.loads((tmp_path / "finalrelease.json").read_text())
    assert release["promote"] is False
    assert len(release["selection_sha256"]) == len(release["evaluation_sha256"]) == 64
    with pytest.raises(FileExistsError):
        evaluate_frozen(
            selection, tmp_path / "another-report.json", bootstrap_samples=10, allow_partial=True
        )


def test_unfrozen_selection_is_rejected_before_test_file_is_opened(tmp_path):
    import json

    from training.evaluate import evaluate_frozen

    selection = synthetic_frozen_selection(tmp_path)
    body = json.loads(selection.read_text())
    body["status"] = "TUNING"
    selection.write_text(json.dumps(body))
    (tmp_path / "test.jsonl").unlink()
    with pytest.raises(ValueError, match="SELECTION_NOT_FROZEN"):
        evaluate_frozen(selection, tmp_path / "report.json", allow_partial=True)
    assert not (tmp_path / "test-evaluation.started.json").exists()


def test_missing_test_hash_is_rejected_after_frozen_access_marker(tmp_path):
    from training.evaluate import evaluate_frozen

    selection = synthetic_frozen_selection(tmp_path)
    with (tmp_path / "test.jsonl").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="DATASET_HASH_MISMATCH"):
        evaluate_frozen(selection, tmp_path / "report.json", allow_partial=True)
    assert (tmp_path / "test-evaluation.started.json").exists()
    assert not (tmp_path / "report.json").exists()


def test_simple_completion_loss_includes_valid_cases_without_feasibility_witness():
    from training.evaluate import _pairs, score_policy

    data = row()
    data["known_feasible"] = False
    for result in data["policy_results"]:
        if result["policy"] == "warm_cp_sat":
            result.update(validated=False, status="UNKNOWN", quality=None)
    learned = score_policy([data], lambda _: True)
    simple = score_policy([data], "greedy")
    assert _pairs(learned, simple)[1] == 1


def test_selected_model_and_threshold_are_not_replaced_by_better_test_candidate(tmp_path):
    import hashlib
    import json

    from planner.ml.manifest import ModelArtifact
    from training.evaluate import evaluate_frozen

    selection_path = synthetic_frozen_selection(tmp_path)
    model = ModelArtifact(
        kind="logistic",
        mean=(0.0,) * len(FEATURE_NAMES),
        scale=(1.0,) * len(FEATURE_NAMES),
        coefficient=(0.0,) * len(FEATURE_NAMES),
        intercept=1.0,
    )
    model_path = tmp_path / "model.json"
    model_path.write_text(model.model_dump_json(), encoding="utf-8")
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    selected = json.loads(selection_path.read_text())
    selected.update(
        status="SELECTED",
        model_path="model.json",
        model_sha256=model_hash,
        threshold=0.5,
        candidate_models={
            "alternate": dict(model_path="model.json", model_sha256=model_hash, threshold=0.99)
        },
    )
    selection_path.write_text(json.dumps(selected), encoding="utf-8")
    report = evaluate_frozen(
        selection_path, tmp_path / "report.json", bootstrap_samples=10, allow_partial=True
    )
    assert report["policies"]["learned"]["records"][0]["selected_policy"] == "warm_cp_sat"
    assert report["policies"]["alternate"]["records"][0]["selected_policy"] == "greedy"
    assert report["classification"]["learned"]["threshold"] == 0.5
    release = json.loads((tmp_path / "finalrelease.json").read_text())
    assert release["threshold"] == 0.5
    assert release["model_sha256"] == model_hash
    assert release["promote"] is False


def test_measurement_limitation_is_an_additional_release_veto(tmp_path):
    import json

    from training.evaluate import evaluate_frozen

    path = synthetic_frozen_selection(tmp_path)
    selection = json.loads(path.read_text())
    selection["measurement_limitations"] = ["WINDOWS_CHILD_TREE_DEADLINE_NOT_ENFORCED_V2"]
    path.write_text(json.dumps(selection), encoding="utf-8")
    report = evaluate_frozen(
        path, tmp_path / "report.json", bootstrap_samples=10, allow_partial=True
    )
    assert "MEASUREMENT_SUPERVISION_LIMIT" in report["decision"]["failed_gates"]
    assert report["measurement_limitations"] == selection["measurement_limitations"]


def test_frozen_benchmark_cp_sat_name_is_the_cold_baseline():
    from training.evaluate import score_policy

    data = row(repeats=2)
    expected = score_policy([data], "cold_cp_sat")
    for result in data["policy_results"]:
        if result["policy"] == "cold_cp_sat":
            result["policy"] = "cp_sat"
    assert score_policy([data], "cold_cp_sat") == expected


def test_cold_alias_collision_is_rejected_instead_of_silently_overwriting():
    from training.evaluate import score_policy

    data = row()
    cold = next(r for r in data["policy_results"] if r["policy"] == "cold_cp_sat")
    data["policy_results"].append({**cold, "policy": "cp_sat"})
    with pytest.raises(ValueError, match="DUPLICATE_POLICY_REPEAT"):
        score_policy([data], "cold_cp_sat")


def test_audited_correction_preserves_choices_records_and_original_report(tmp_path):
    import hashlib
    import json

    from training.correct_policy_alias import correct
    from training.evaluate import evaluate_frozen, score_policy

    selection_path = synthetic_frozen_selection(tmp_path)
    selection = json.loads(selection_path.read_text())
    test_path = tmp_path / "test.jsonl"
    data = json.loads(test_path.read_text())
    for result in data["policy_results"]:
        if result["policy"] == "cold_cp_sat":
            result["policy"] = "cp_sat"
    test_path.write_text(json.dumps(data) + "\n")
    selection["artifacts"]["test"]["sha256"] = hashlib.sha256(test_path.read_bytes()).hexdigest()
    selection_path.write_text(json.dumps(selection))
    report = evaluate_frozen(
        selection_path, tmp_path / "source.json", bootstrap_samples=10, allow_partial=True
    )
    report["policies"]["learned"] = report["policies"]["simple_router"]
    report["uncertainty"]["simple_router"] = {"mean_improvement_ci_ms": [0, 0]}
    report["decision"] = {
        "promote": False,
        "failed_gates": ["INSUFFICIENT_PAIRED_EVIDENCE", "MEASUREMENT_SUPERVISION_LIMIT"],
    }
    missing = {
        **data,
        "policy_results": [r for r in data["policy_results"] if r["policy"] != "cp_sat"],
    }
    report["policies"]["cold_cp_sat"] = score_policy([missing], "cold_cp_sat")
    original = tmp_path / "original.json"
    original.write_text(json.dumps(report))
    before = original.read_bytes()
    marker = (tmp_path / "test-evaluation.started.json").read_bytes()
    output = tmp_path / "corrected.json"
    correct(original, selection_path, output)
    corrected = json.loads(output.read_text())
    assert corrected["policies"]["cold_cp_sat"]["missing_result_count"] == 0
    assert corrected["policies"]["learned"] == report["policies"]["learned"]
    assert corrected["policies"]["simple_router"] == report["policies"]["simple_router"]
    assert corrected["decision"]["promote"] is False
    assert "MEASUREMENT_SUPERVISION_LIMIT" in corrected["decision"]["failed_gates"]
    assert original.read_bytes() == before
    assert (tmp_path / "test-evaluation.started.json").read_bytes() == marker
    with pytest.raises(FileExistsError):
        correct(original, selection_path, output)
