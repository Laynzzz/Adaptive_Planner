# Routing experiment: negative deployment decision

Local synthetic experiment, 2026-09-25. **Do not promote. Fixed-policy serving remains the default.** The experiment completed; superiority was not demonstrated. CPU was sufficient for these small tabular models; no GPU or paid provider was used.

## Frozen design and provenance

1,000 base groups were generated and measured in a frozen 53.20-minute run: 600 train / 200 validation / 200 test. Seven thousand requested executions include two repeats of greedy, cold CP-SAT and greedy-warm CP-SAT, plus a longer reference. The primary native solve budget was 200ms; child startup, construction, validation and feature time were separately retained and included in total latency. This is a shared Windows i7-13700K machine, not isolated production capacity. See the scheduler report and frozen manifest for complete budgets and environment.

Training used 18 serving-available features, StandardScaler fitted only to known training labels, LogisticRegression(C=1,max_iter=1000) and GradientBoostingClassifier(50 trees, depth 2, learning rate .1). Seed: 20260925. Python3.12.14 / scikit-learn1.9.1 / NumPy2.5.3 / OR-Tools9.15.6755. Only 67 of 600 training groups had reliable binary labels; unknown/censored outcomes were retained in policy evaluation, not converted to negative labels.

Validation selected logistic regression at probability threshold .9. The simple rule escalates when utilization >= .75, minimum slack <= 0, or greedy quality < .5 (exact comparisons are frozen in code). Both also force escalation for invalid greedy results. No candidate met every validation completion/tail-quality condition; selection identifies the candidate for reporting and does not authorize deployment. The frozen selection records all trials, preprocessing, configurations, hashes and environments.

The selection SHA256 is `4f7b0e0396150d8f1b2d6e4590b33131979f3ade97780b5493a7707f9bb4b35f`. It was written before the one-time test invocation. Test artifact SHA256: `9e121946bae7ce9814871b698c2065717b5f026a059baf0ab24cc281ad9bfe0b`. No model, threshold, features or rule were changed using test results.

## Held-out policy results

These are observational replays of measured alternatives, with measured inference/artifact-load overhead added; they are **not fresh routed end-to-end executions**. Each primary policy has 400 attempts across200 groups. A completion means an independently valid schedule, not necessarily an optimum. Quality losses only have meaning on paired valid outcomes; failed attempts remain in the completion denominator.

| Policy | Valid / attempts | Total p50 ms | Total p95 ms | Mean quality loss | Worst-decile loss |
| --- | ---: | ---: | ---: | ---: | ---: |
| Greedy | 104/400 | 682.69 | 858.03 | .00215 | .01593 |
| Cold CP-SAT | 171/400 | 880.13 | 1007.08 | .03568 | .20199 |
| Warm CP-SAT | 167/400 | 876.70 | 1012.20 | .01530 | .11779 |
| Simple router | 167/400 | 869.74 | 1004.48 | .01545 | .11779 |
| Selected logistic router | 167/400 | 875.38 | 1012.20 | .01530 | .11779 |
| Frozen boosted alternative | 167/400 | 875.33 | 1010.38 | .01530 | .11779 |
| Longer requested reference | 126/200 | 1281.71 | 1390.14 | .00047 | .00460 |

Zero invalid candidates were accepted. The learned policy lost85 attempts for which a valid reference/baseline result was known; it lost none relative to the simple router. Its p95 was .51% worse than cold CP and .77% worse than the simple router, missing the required20%/10% improvements. Its worst-decile quality loss .11779 exceeded .05. The paired mean-latency improvement versus the simple router had a95% interval of **[-25.89,-9.57]ms**: it was slower. Bootstrap used2,000 draws of base groups, keeping repeats together.

The classifier had20/20 correct known test labels, but **all20 were negatives and180/200 groups had unknown labels**. This establishes no positive-class detection ability and is not a useful standalone accuracy claim. Family breakdowns, calibration, confusion counts, CPU measurements, missing counts and uncertainty are retained in the [summary](raw/ml-test-summary.json) and [full corrected report](raw/ml-evaluation-corrected.json).

## Measurement defect and audited report correction

Two distinct problems remain visible:

- Windows virtual-environment launcher descendants were not reliably terminated by the v2 controller's direct-child timeout. The full run retains two WALL_TIMEOUT outcomes and all original measurements. The production process-tree supervisor is now fixed and tested on Windows/Linux; that does not retroactively validate old timing. `MEASUREMENT_SUPERVISION_LIMIT` independently forbids promotion. A repaired v3 smoke is separate evidence; the full v3 experiment has not been executed.
- The first held-out report expected the baseline key `cold_cp_sat`, while the frozen runner wrote `cp_sat`. It incorrectly marked all400 cold outcomes missing. The [original report](raw/ml-evaluation-original.json), original marker and denied release are preserved. A failing synthetic regression reproduced the adapter mismatch. The fix canonicalizes before duplicate detection. `training.correct_policy_alias` recomputed only cold records and dependent statistics from the same raw rows, preserving every model/simple result and inference measurement byte-for-byte in value. It did not refit, reselect, repeat classifier inference or rerun solvers. The corrected report records original-report, selection and correction-script hashes. This is an explicit arithmetic correction after unsealing, not a second untouched test.

Final failed gates: `REFERENCE_COMPLETION_LOSS`, `TAIL_QUALITY_LOSS`, `ALWAYS_CP_P95_GAIN`, `SIMPLE_P95_GAIN`, `LATENCY_UNCERTAINTY`, `MEASUREMENT_SUPERVISION_LIMIT`. No learned release was enabled. The upper200-task input limit is not a proven performance envelope: none of the primary policies completed a200-task run under these benchmark budgets.

## Reproduction and serving

Exact small selection/model artifacts are in `training/artifacts/v2/`; original full measurements (333MB) and derived splits are intentionally retained under ignored `.runtime/`, with hashes in manifests. Frozen source ZIPs under `benchmarks/artifacts/` allow rebuilding the original measurement code. A fresh run will produce different wall-time hashes; it is a new experiment, not the original one. Do not describe a later test of these same scenarios as untouched.

```powershell
uv run python -m training.train --dataset-manifest .runtime/training/v2/manifest.json --output-dir .runtime/training/v2/experiment
uv run python -m training.evaluate --manifest .runtime/training/v2/experiment/selection.json
uv run python -m training.correct_policy_alias --original .runtime/training/v2/experiment/test-evaluation.json --selection .runtime/training/v2/experiment/selection.json --output .runtime/training/v2/experiment/test-evaluation-corrected.json
uv run pytest tests/unit/test_features.py tests/unit/test_training.py tests/unit/test_model_artifact.py tests/unit/test_policy_evaluation.py tests/unit/test_promotion.py tests/integration/test_routing.py tests/fault/test_model_rollback.py -q
```

The first three commands describe the recorded run and intentionally refuse to overwrite its existing outputs. With the repaired evaluator, a new experiment no longer needs the alias correction. Keep the frozen originals intact. The committed original `finalrelease.json` remains denied and refers to the original report; it is a provenance artifact, not a serving recommendation.

Production defaults to `PLANNER_ROUTING_MODE=fixed`, with its separate2-second native solver budget. Shadow mode observes decisions without selecting a different plan. Learned mode requires a hash-pinned, trusted, promoted release; unavailable, mismatched or unpromoted artifacts fall back to the fixed policy. The independent validator still controls acceptance. Current benchmark data do not establish the latency or completion rate of that2-second production setting.

