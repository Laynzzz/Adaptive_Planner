# Task15: Independent feature/artifact review and frozen policy evaluation

2026-09-25. Review and unit work used code and synthetic temporary rows only. No
benchmark test outcome file was opened during implementation. Root owns final model
selection and the model card; final evaluation requires the frozen selection first.

## Review findings

The shared feature builder uses normalized inputs and the already computed greedy
candidate. It does not access future CP quality/runtime. Feature order and finite
values are checked. DAG traversal is bounded, prior UTC timestamps are mapped to the
current slot origin, and supervised fitting uses known labels from train only.
The artifact loader resolves a trusted root, verifies a pinned SHA256, limits file
size and accepts constrained JSON rather than executable pickle. Tree children must
have increasing indices, preventing cycles. Promotion gates are separate from
model selection, with exact boundary tests.

One concrete export correctness defect was reproduced with synthetic data:

- `StandardScaler(with_mean=False)` plus logistic regression exported different
  preprocessing, causing a maximum probability difference of0.9150.
- `GradientBoostingClassifier(loss='exponential')` requires a different probability
  link; the generic exporter used the default logistic link, producing a maximum
  difference of0.1537.

The exporter now rejects unsupported scaler flags, boosting loss and initializer.
The configured default estimators retain held-out synthetic prediction parity.
Three negative tests failed before repair; six artifact tests passed afterward.
Raw evidence: `raw/task-15-exporter-red.txt`, `raw/task-15-exporter-green.txt`.

Root was also notified to freeze code/environment/objective/solver/hyperparameter
provenance in addition to data/split hashes, and to reject missing-latency candidates
in validation ranking. Frozen features were not changed while benchmarks ran.

## Evaluator contract

`training.evaluate.score_policy(rows, chooser)` takes a fixed baseline name or a
callable receiving only the ordered serving-available feature dictionary. Invalid
or missing greedy results bypass the classifier and select warm CP. All attempts
remain in the result records, including UNKNOWN, errors, rejected invalid schedules,
missing results and unknown supervised labels. Missing timing is null, not zero.

Quality loss is positive reference-minus-policy on paired valid results; signed
policy-minus-reference differences are also reported. The best validated measured
reference/baseline provides reference quality. Completion losses versus that reference
are counted on known-feasible attempts. Completion losses versus the simple router
also count valid baseline successes without a generator feasibility witness.

Timing replays the measured selected greedy or warm result, so warm greedy/features/
startup are counted once. Measured inference and artifact loading are added. This
is observational policy replay with approximated per-decision loading overhead,
not a claim of newly measured routed subprocess or HTTP latency. Requested reference
execution timing is reported once per scenario rather than fabricating repeated runs.

Base-group paired bootstrap retains all repeats/variants within each resampled group.
It reports a95% percentile interval for mean latency improvement and a separate
p95-gain interval. Resource checks bound groups/rows, per-row repetitions, artifact
size, line size and bootstrap resampling work. A missing timing value prevents
promotion instead of making a favorable average silently exclude it.

CLI: `uv run python -m training.evaluate --manifest <frozen-selection.json>`.
The evaluator loads the selected model/threshold and frozen simple rule, verifies
hashes and disjoint groups, records selection/test hashes before test access, and
creates an exclusive experiment marker. It never chooses among candidates using
test outcomes. Both frozen candidate models can be reported, but only the selected
one is evaluated for promotion. Output includes classification counts/calibration,
per-family policy summaries, failures/unknowns, bootstrap uncertainty and gate codes.
`finalrelease.json` pins selection/evaluation/model hashes and preserves the frozen
threshold; it does not activate learned serving. Development partial data always
denies promotion. Insufficient training labels produce an explicit negative result.

## Verification

`raw/task-15-evaluation-red.txt`: five missing-module failures before implementation.
`raw/task-15-evaluation-boundary-red.txt`: completion loss on an unwitnessed-but-valid
baseline initially went uncounted; the regression drove the correction.

`raw/task-15-evaluator-final.txt`:31 synthetic evaluator/training/artifact/promotion
tests passed in7.01s on the final rerun. Cases cover failures/unknowns, greedy bypass, no duplicated
warm timing, grouped repeats, no future outcome fields supplied to a chooser,
freeze-before-test access, one-time evaluation markers, hash rejection and refusing
to replace a frozen model/threshold with a faster test candidate.

## Post-evaluation adapter correction

After root froze selection and authorized the one-time 200-group evaluation, the
original report marked all cold-policy results missing. Root and this reviewer
independently found the same adapter error: frozen raw rows name that baseline
`cp_sat`, while the evaluator expected `cold_cp_sat`. The unit fixtures had used
only the latter name. This was an evaluator integration defect, not missing
benchmark executions.

Root added an alias before duplicate detection and produced the separately named
`test-evaluation-corrected.json` using `training/correct_policy_alias.py`. Review
confirmed the selection hash and complete learned/simple/greedy/warm policy
objects are unchanged; no fitting, selection, threshold tuning or repeated
classifier inference occurred. Only the cold records and dependent comparisons
were recomputed. The original report and exclusive evaluation marker remain.

Corrected v2 decision is **do not promote**. It retains the independent
`MEASUREMENT_SUPERVISION_LIMIT` veto and also fails reference-completion,
tail-quality, always-CP p95, simple-rule p95 and latency-uncertainty gates.
Learned versus simple paired mean-improvement 95% interval is
[-25.88698, -9.56817] ms; negative means learned routing was slower in this
observational replay. The repaired process supervisor requires a new experiment.
These results do not establish a learned routing improvement or authorize serving.
