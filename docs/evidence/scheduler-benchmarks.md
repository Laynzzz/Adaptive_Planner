# Scheduler benchmark and dataset evidence — Task 14

The v2 experiment is **ineligible for deployment promotion** because its original Windows timeout code terminated only the direct subprocess, allowing descendants to escape a deadline. The issue was reproduced with a real grandchild marker after the measurement began. All original runs, including missing outcomes, are preserved. A repaired v3 source release uses atomic Windows job assignment and POSIX process groups; v3 requires separate measurements rather than relabeling v2 evidence.

## Workload and frozen protocol

The AI-assisted synthetic generator produces 1,000 independent base groups: 600 train, 200 validation and 200 sealed final test. Repeats stay inside their base group. Seed is 20260925, with deterministic per-group seeds. Normal cases contain 20, 50, 100 or 200 tasks; tiny exhaustive cases contain three tasks over eight slots. Normal horizons contain 1,344 fifteen-minute slots (14 days). Work varies in slack, fragmentation, dependency density, protected fraction, priorities and the fraction of work represented by a prior candidate. Final groups 900–999 reserve a fragmented, dense-dependency parameter combination. All dates are synthetic UTC; this is not representative human behavior or a distribution of real user workloads. Timezone/DST correctness is tested elsewhere, not estimated by these timing fixtures.

Known-feasible cases carry a constructed witness checked by the independent production validator. Separate infeasible cases require at least two slots before deadline slot one. Named zero-budget controls preserve unknown-search outcomes. Witness validity does not imply a particular heuristic finds a solution. Horizons and prior-work edits are simplified; most ordinary work ends before the 14-day boundary and the previous candidate covers only part of the current task set.

Every group executes greedy, cold CP-SAT and warm-start CP-SAT twice in a seeded shuffled order, then one reference execution: 7,000 requested process runs. Cold CP-SAT explicitly disables greedy hints and fallback. Warm CP-SAT receives its measured, validated greedy result and deducts greedy/feature time from the native allowance. Main policies share a two-second end-to-end process allowance and 200 ms requested native CP allowance; reference allowance is four seconds and 600 ms native. Native time is not the whole latency budget: model construction, validation, imports, serialization and process startup are measured too. Tiny references enumerate candidates exhaustively. A time-limited longer search is only best-known; optimality requires an OPTIMAL result or exhaustive tiny proof.

The coordinator has two slots and a 90-minute run cap with per-case atomic checkpoint writes. V2's Windows descendant cleanup flaw means those slots cannot be claimed as an enforced hard CPU cap. Zero-budget controls intentionally request zero native CP time. Missing child output, crashes, unknowns and wall timeouts retain their rows and measured end-to-end latency; unavailable killed-child CPU/RSS remains unknown, never zero. Early v1 telemetry returned zero Windows RSS because a ctypes handle signature was wrong; that run was stopped, preserved as failed instrumentation, and replaced by v2 after positive-RSS smoke checks.

## Provenance and timing

The shared local host is Windows 11, Intel Core i7-13700K (16 cores / 24 logical), Python 3.12.14, OR-Tools 9.15.6755. Exact package versions and the observed lockfile hash are in [environment evidence](raw/measurement-environment.json). The scheduler ran alongside local project tests/builds and the two-slot HTTP worker study; this was not a quiet dedicated benchmark machine. Seeded per-case policy order reduces but does not remove shared-host effects.

`benchmarks/manifests/full.json` is the original immutable v2 input (SHA256 `0f3fdb3616c2cf4fc9583d31079a1d8ecc934f36ff8c560af2bfd552a56f92c1`). Seventy-four original source files are byte-hashed and bundled in `benchmarks/artifacts/scheduler-v2-sources.zip`. V3 separately freezes 100 source files, including repaired process supervision. `source-releases.json` hashes every archive and source member. Targeted Git attributes preserve immutable manifest bytes and binary archives. The CLI restores and uses the frozen controller as well as the child implementation, avoiding accidental reproduction with a newer coordinator.

Measured components are startup/import, greedy, feature computation, CP model construction, native solve, validation, process/transport residual, whole-run elapsed time, process CPU and peak RSS. Feature computation uses the same 18 named features as serving and contains no future CP outcome. Greedy-only measurements include feature construction in the raw experiment; routing-policy replay must explicitly account for which features it actually executes. CPU and peak RSS are per measured child, not total host utilization.

## Labels, denominators and access boundary

`training/build_dataset.py` selects the best validated measured reference across the reference execution and repeated baselines. A valid greedy result gets a positive label only when that measured improvement exceeds 0.02. A negative label requires an optimum proof within tolerance. A time-limited search with no improvement is censored/unknown, not a negative label. Invalid or missing greedy/reference cases remain present with an explicit reason. Supervised fitting excludes unknown labels; policy evaluation must retain all groups.

Derived rows contain `snapshot`, 18-feature dictionary, first-repeat greedy result, selected reference plus requested reference, all six policy results, family/seed/group/split parameters, witness provenance and label reason. Immutable split manifests record hashes, feature order, measurement-manifest hash and measurement limitations. V2 derived manifests carry `WINDOWS_CHILD_TREE_DEADLINE_NOT_ENFORCED_V2` and deny deployment eligibility regardless of statistical results. The model-selection and final-evaluation implementation additionally treats that limitation as a failed promotion gate.

`benchmarks.analyze` reports all run/status counts, known-feasible completion, missing/invalid counts, paired positive and signed quality loss, worst-decile loss, p50/p95 elapsed/CPU/RSS and stage/family/task-count slices. Paired quality averages use only valid pairs and show their denominator; missing results never improve an average by disappearing. Repeated rows are correlated. Model promotion and grouped uncertainty are evaluated separately by the routing experiment. Final per-case outcomes remain sealed until its configuration is frozen.

## Run status and verification

V2 finished **1,000/1,000 groups and all 7,000 requested execution records in 3,192.08 seconds (53.20 minutes)**. The dataset contains exactly 600/200/200 groups. Final outcomes were unsealed only after routing selection SHA256 `4f7b0e0396150d8f1b2d6e4590b33131979f3ade97780b5493a7707f9bb4b35f` was frozen and the one-time evaluation completed. This analysis did not alter that selection or rerun its evaluator.

There are 960 witnessed-feasible groups, 40 constructed infeasible groups, 100 tiny groups and 40 zero-budget controls (the latter two are subsets of witnessed-feasible). The requested references produced 678 valid candidates, 282 UNKNOWN results and 40 INFEASIBLE results. Only 107 have optimality proofs: 100 exhaustive tiny cases and seven CP-SAT OPTIMAL results. Two warm-policy wall timeouts remain in the 7,000 records. No validated result was marked invalid.

| Baseline | Valid / all runs | Valid / known-feasible runs | Paired quality n | Mean positive loss | Worst-decile loss | p50 / p95 elapsed ms | p95 CPU ms | p95 peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| greedy | 770/2000 | 770/1920 | 770 | 0.00293 | 0.02552 | 721.25 / 920.34 | 625.00 | 86.35 |
| cp_sat | 883/2000 | 883/1920 | 883 | 0.05927 | 0.29668 | 904.05 / 1092.31 | 781.25 | 109.57 |
| warm_cp_sat | 936/2000 | 936/1920 | 936 | 0.01517 | 0.12191 | 909.85 / 1096.34 | 796.88 | 109.18 |

Signed reference-minus-policy means equal the positive means here because the best-known reference pool includes every measured baseline candidate. The small greedy conditional loss does **not** establish adequacy: 1,230/2,000 greedy runs did not produce a valid candidate. CPU/RSS denominators are 2,000 for greedy/cold and 1,998 for warm because the two killed children lack those measurements.

| Task count | Greedy valid/all | Cold CP valid/all | Warm CP valid/all |
| --- | ---: | ---: | ---: |
| 3 | 200/200 | 200/200 | 200/200 |
| 20 | 352/400 | 360/400 | 378/400 |
| 50 | 208/500 | 323/500 | 348/500 |
| 100 | 10/400 | 0/400 | 10/400 |
| 200 | 0/500 | 0/500 | 0/500 |

**The measured short-budget envelope does not reliably solve the 100/200-task synthetic families.** No baseline completed a 200-task run; cold CP completed no 100-task run. The product storage limit of 200 active tasks is not a demonstrated solvability or latency guarantee. Even 20/50-task groups include unknown/infeasible outcomes. These results support explicit bounded failure/UNKNOWN handling and invalidate a broad performance-success claim. Family, split and task-count slices are preserved in the aggregate JSON.

| Component p95 ms | Greedy | Cold CP | Warm CP |
| --- | ---: | ---: | ---: |
| startup_import_ms | 650.542 | 648.993 | 650.969 |
| greedy_ms | 108.041 | 0.000 | 108.924 |
| feature_ms | 24.579 | unmeasured / not executed | 24.639 |
| model_build_ms | 0.000 | 73.830 | 73.397 |
| native_solve_ms | 0.000 | 209.892 | 200.418 |
| validation_ms | 0.409 | 0.472 | 0.561 |

Percentiles from different components do not sum to the total percentile. Process/transport residual p95 is 187.76/188.85/191.66 ms for greedy/cold/warm; imports account for roughly another 650 ms p95. This fresh-Windows-process experiment is dominated in part by startup and does not estimate a hypothetical persistent solver service.

| Split | Positive labels | Proven negative | Unknown / excluded from fit |
| --- | ---: | ---: | ---: |
| train | 7 | 60 | 533 |
| validation | 4 | 20 | 176 |
| test | 0 | 20 | 180 |

The final split has no observed positive supervised label and 180 unknown labels. That is weak evidence for classification or calibration; the routing evaluator rejected promotion for insufficient paired evidence as well as the supervision limitation. Detailed classifier selection/results are reported separately by the ML experiment, not substituted for these baseline denominators.

Initial v2 smoke completed five training-only groups in 11.56 seconds. After the supervision repair, **v3 smoke completed seven groups / 28 executions in 13.16 seconds**, covering tiny and 20/50/100/200 tasks, infeasible and zero-budget controls: zero child errors, zero invalid candidates, and 28 positive peak-RSS measurements. UNKNOWN search outcomes remain expected and explicit. The real descendant deadline regression separately verifies containment; this smoke is not a full v3 experiment. Full v3 has not been run.

Artifacts: [full result manifest](../../benchmarks/manifests/full-v2-results.json), [dataset manifest](../../training/manifests/dataset-v2.json), [all baseline aggregates](raw/scheduler-baselines-v2.json), [label/reference/error diagnostics](raw/scheduler-diagnostics-v2.json), [training/validation-only earlier analysis](raw/scheduler-train-validation.json), [repaired smoke](raw/scheduler-v3-smoke.json). Full raw SHA256: `1ff71e148dc93257213cb6cde0175783b4299b09ee1eeff965a22b80d07d56b9`.

Tests validate all 1,000 witnessed generators and disjoint groups. The summary regression first failed before implementation and then verified timeout/invalid results remain in total and known-feasible denominators. The supervision regression first observed an actual escaped descendant after a 350 ms deadline, then passed using the repaired shared utility. Raw [metric red](raw/task-14-analysis-red.txt), [metric/split green](raw/task-14-analysis-green.txt), [supervision red](raw/task-14-supervision-red.txt) and [supervision green](raw/task-14-supervision-green.txt) are retained. Production process-tree fault tests additionally exercise cancellation, parent exit, supervisor exit and callback failure on Windows and Linux.

```powershell
uv run python -m benchmarks.restore scheduler-v2
uv run python -m benchmarks.run --manifest benchmarks/manifests/smoke.json --output .runtime/benchmarks/smoke-v2-rerun.jsonl
uv run python -m benchmarks.run --manifest benchmarks/manifests/full.json --resume
uv run python -m training.build_dataset --input .runtime/benchmarks/full-v2.jsonl --output-dir .runtime/training/v2 --measurement-manifest benchmarks/manifests/full.json
uv run python -m benchmarks.analyze --input .runtime/benchmarks/full-v2.jsonl --output docs/evidence/raw/scheduler-train-validation.json
uv run python -m benchmarks.restore scheduler-v3
uv run python -m benchmarks.run --manifest benchmarks/manifests/smoke-v3.json
# Full v3 is separately versioned; not claimed as executed by the v2 report.
uv run python -m benchmarks.run --manifest benchmarks/manifests/full-v3.json
```

Choose new output paths for reruns; checkpoints reject a different manifest. Add `--include-final` to analysis only after routing configuration freeze. Full raw snapshots/results stay in ignored local runtime storage because they are large; committed manifests, source bundles and summaries identify them and the commands regenerate them. No paid provider call, GPU or cloud resource was used.

Teaching points: feasibility witnesses separate generator correctness from solver success; longer searches provide bounds rather than automatic truth; censoring changes supervised labels; shared-host startup costs can dominate algorithm time; process containment is part of a resource-budget claim; failed promotion gates should result in a simpler deployed policy, not hidden denominator changes. Read `benchmarks/generate.py`, `benchmarks/run.py`, `benchmarks/child.py`, `training/build_dataset.py` and the source-release manifests.
