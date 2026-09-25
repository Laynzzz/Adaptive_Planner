# Tasks 9–10: reviewed extraction and frozen mock evaluation

Date: 2026-09-25. Source baseline before this slice: `7bb57b9714cb3df69a9a369a711726fcc7276ac6`; the introducing commit contains the implementation and this evidence. Local Windows, Python 3.12.14, PostgreSQL 17.9 and real Keycloak fixture. No paid model request was made. HTTP provider tests use HTTPX MockTransport; integration tests use real isolated PostgreSQL databases and real local OIDC authentication.

## Implemented behavior and explicit limits

The API persists a queued interpretation and returns immediately. `uv run python -m planner.ai.worker` runs a separate two-slot I/O pool (the calendar worker receives the other two slots of the local four-slot I/O budget). PostgreSQL enforces one queued/running interpretation per owner; a dispatcher advisory lock bounds running claims across worker processes. A 35-second lease and fencing token prevent late results from publishing. The provider invocation has a 30-second total timeout, with at most one retry for transport failures, HTTP 429 or server errors. A terminated worker's expired claim becomes a persisted `WORKER_INTERRUPTED` failure; it is not silently retried as a new paid request.

The OpenAI Responses adapter sends the selected text, explicit reference clock/timezone, versioned instructions and strict JSON schema. It has no tools and uses `store=false`. It handles authentication errors, refusal, incomplete/malformed output, timeout and unavailability as errors. This implementation follows the official [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) and [text generation guide](https://developers.openai.com/api/docs/guides/text). The live adapter was exercised with synthetic HTTP responses only; provider/model compatibility and live output quality remain unverified.

Live mode defaults off. Enabling it requires separately configured API credentials, model identifier, approval reference, positive budget, positive input/output unit prices and dated price assumptions. A transaction verifies the claim's ownership, fence, state and remaining lease, then reserves a conservative two-attempt maximum before invocation. The bound uses serialized UTF-8 input bytes plus a protocol allowance and the output-token cap. Actual single-attempt token usage settles the reservation. Failed/retried calls with incomplete usage conservatively consume the reservation while reported actual cost remains null. A failed or expired claim cannot reserve again. The reservation is a local conservative accounting control dependent on accurate configured pricing; no price or dollar allowance was assumed.

Proposals preserve explicit/inferred/unknown labels, exact source spans, and confirmation requirements. Parsing rejects malformed schemas, fabricated spans, invalid dates/timezones, out-of-range durations/priorities, more than 20 tasks, missing proposed dependency references, cycles and soft-to-hard evidence contradictions. Inputs are limited to 8,000 characters. Relative dates use the recorded reference clock. Acceptance revalidates the proposal and requires overrides for selected unknown fields, confirmation for inferred fields, and resolution of global contradictions. Selected dependencies must be included. A single revision/idempotency transaction creates the reviewed batch, dependency edges, audit, receipt and coalesced replan intent. Model output alone cannot modify tasks or publish a calendar. Cross-owner records return 404; stale interpretations return 409.

Weekday soft preferences, recurring hard unavailability and no-deadline weekdays are now persisted through the same reviewed revision transaction. The review explicitly selects or deselects each rule and confirms every selected rule; rule-only batches are supported. Task/rule conflicts roll back the whole batch. Acceptance verifies matching weekday evidence and supported English intent cues, so a fabricated hard rule cannot pass merely because a checkbox was checked. Unsupported wording and unknown rule intent require clarification or the explicit manual rule editor. Hard unavailability expands into busy intervals; soft avoidance changes preferred windows; no-deadline weekdays reject conflicting active deadlines. Source evidence remains a provenance check rather than proof of interpretation correctness. This closes the previously recorded weekday-persistence deferral without changing the frozen extraction provider/schema/prompt/scorer.


## Red/green verification

- Initial semantic-validation tests failed because fabricated evidence, dependency cycles and soft-to-hard reinterpretation were accepted. Source-span, DAG and contradiction checks made those tests pass.
- The first spend-guard test reached the mocked HTTP transport twice with no reservation. It now raises `SPEND_RESERVATION_REQUIRED` before any transport call.
- The exact scoring tests initially returned `0/0`; failures asserted a required critical denominator of 3 and retained schema-failure denominator of 1. The scorer now counts correct, incorrect, missing, unknown and invented values explicitly.
- A reviewed proposal with `conflicting_request` initially returned HTTP 200 despite unresolved global uncertainty. Acceptance now returns 422 and leaves revision/tasks unchanged.
- An expired live claim initially invoked the fake provider once after reconciliation. [Raw failing regression](raw/ai-expired-live-red.txt) records that result. The reservation now checks the live fence/lease first; the regression verifies zero calls.
- The first queue integration run failed because migration 7 had not yet been added. That was a schema setup failure, not evidence of application behavior. The final fixture migrates each fresh isolated database through the complete current chain.
- `uv run pytest tests/unit/test_interpretation.py tests/unit/test_eval_metrics.py tests/integration/test_accept_interpretation.py -q`: **33 passed in 10.30s**, [raw output](raw/ai-tests-green.txt). Coverage includes malformed/cyclic provider data, guessed durations, ambiguity, stale revisions, rollback of a partially invalid batch, dependencies, replay, ownership, disabled live mode/manual forms, retry limits, total timeout, lease recovery and spend limits.
- Named `test_adversarial_hard_constraints_suite_rejects_every_acceptance`: **0 accepted / 3 attempts** (invented busy rule, invented no-deadline rule and soft-to-hard escalation). This is a deterministic acceptance-control result, not a claim about live model hallucination rates.
- Scoped Ruff on AI/API/model/migration/evaluation modules and dedicated tests: passed. Frozen data/prompt/schema/implementation hash verification: passed.
- Root's separate browser verification: `tests/e2e/interpretation.spec.ts`, **1 passed in 7.7s** with real local OIDC, PostgreSQL and `ai.worker`. Ambiguous next Thursday required explicit no-deadline choice plus priority confirmation; task creation happened after acceptance. An injected HTTP 503 preserved text and manual entry. The later R2 browser run passed **4 tests in 23.0s**, including a rule-only “I dislike Sundays” review, confirmation, persisted manual-rule display after reload, and removal. The complete frontend suite passed **19 tests** with typecheck/build passing. [Browser capture](raw/interpretation-fallback.png).

## Frozen data and provenance

[Manifest](../../evals/data/manifest.json) version `synthetic-extraction-v1` contains SHA256 hashes for all three data files, prompt, response schema, model configuration, authoring script and evaluation-relevant implementation. Manifest SHA256: `b655379ec2b3c686ad433e8dd60afcdcefbf653f915edecb47a24fb52b24ca15`. The runner verifies hashes and refuses to overwrite prior output. Changes require a separately versioned release and fresh evidence.

There are 120 original synthetic examples: 40 scenario families with three grouped variants each; development has 20 families/60 examples, validation 10/30, final test 10/30. No family crosses splits. They cover relative dates, missing effort, numeric/locale ambiguity, conflicting duration/date requests, three weekday constraint concepts, multiple dependencies, explicit priorities, Unicode, and adversarial instructions. Some constraint-only siblings are repeated identical statements; these counts are correlated and are not 120 independent natural-language observations.

All source text and references are **AI-assisted**, authored for this repository without private or third-party data. References were authored separately from running MockProvider. A separate deterministic checker verifies field types, duration bounds and explicit unit anchors, date validity and text anchors, title anchors, proposed dependency references/DAG, weekday anchors, split membership, IDs and hashes. **Independent human semantic review is PENDING.** These automated checks do not establish that every reference meaning is correct, and the plan's independent/manual reference-review gate is unexecuted.

One fixed `deterministic-demo-v1` configuration was frozen before all three runs. There was no training, prompt search, model comparison, validation-based tuning or held-out tuning. The final test errors have not been used to change this frozen parser. A future improved parser needs a new experiment/version.

## Metric definitions and measured mock results

Critical fields are duration, deadline (including kind/timezone/fold) and predecessor keys for each reference task. Exact match requires the whole value and explicit/inferred/unknown label. A correct null unknown counts as correct uncertainty; a missing field or invalid output counts as incorrect. Full-proposal correctness additionally requires every reference title/priority, no extra fields/constraints, exact clarification set and abstention decision. All schema/semantic failures remain in reference denominators.

An invented field is a predicted non-null value where the reference is unknown or has no such field. A wrong value for a known reference is an exact-match error, counted separately rather than mislabeled as invented. Hard/soft matching counts exact `(kind, weekday)` reference items and reports unmatched predictions. Clarification counts are set-based true positives, false positives and false negatives for required field reviews/global uncertainty. Latency measures the local mock extraction and validation only. Mock tokens and provider cost are zero by construction; live cost remains unmeasured.

| Metric | Development | Validation | Final test |
| --- | ---: | ---: | ---: |
| Critical exact fields | 150/153 (98.04%) | 69/72 (95.83%) | 87/90 (96.67%) |
| All exact fields | 252/255 | 117/120 | 147/150 |
| Full correct proposals | 57/60 | 27/30 | 27/30 |
| Hard/soft classifications | 15/15 | 9/9 | 9/9 |
| Correct unknowns | 12/15 | 9/12 | 12/12 |
| Invented / predicted non-null fields | 3/225 | 3/102 | 0/129 |
| Clarifications TP / FP / FN | 90 / 0 / 3 | 39 / 0 / 3 | 51 / 0 / 0 |
| Correct abstention decisions | 60/60 | 30/30 | 30/30 |
| Required / predicted abstentions | 6 / 6 | 3 / 3 | 3 / 3 |
| Schema/semantic failures | 0/60 | 0/30 | 0/30 |
| Measured local median latency | 0.0595 ms | 0.0527 ms | 0.0591 ms |
| Measured local p95 latency | 0.1289 ms | 0.1991 ms | 0.1722 ms |
| Known mock provider cost | $0 | $0 | $0 |

Final critical field Wilson 95% interval: **90.65%–98.86%**. Fields and siblings are correlated, so that interval is only descriptive. A 2,000-resample family-group bootstrap (seed 20260925) gives **88.89%–100%**; ten final scenario families are far too few for a strong generalization claim. Category-level counts and every prediction/error are retained in the raw reports.

Development/validation errors are conflicting duration alternatives/ranges: the demonstration parser takes one explicit number rather than retaining uncertainty. Final errors are the three corrective-duration variants (`30 minutes, no make that 45 minutes`): it takes the first number. These errors demonstrate why source evidence and schema validity cannot replace review. The final observed mock proportion exceeds the proposed 95% target, but **the real AI accuracy gate is UNEXECUTED** and the lower uncertainty bounds are below 95%. Interpretation remains experimental.

## Reproduction and handoff

```powershell
uv run python -m planner.ai.worker
uv run pytest tests/unit/test_interpretation.py tests/unit/test_eval_metrics.py tests/integration/test_accept_interpretation.py -q
uv run python -m evals.run.evaluate --split dev --mode mock --output docs/evidence/raw/ai-mock-dev-rerun.json
uv run python -m evals.run.evaluate --split validation --mode mock --output docs/evidence/raw/ai-mock-validation-rerun.json
uv run python -m evals.run.evaluate --split test --mode mock --output docs/evidence/raw/ai-mock-test-rerun.json
```

Executed original commands used the same runner without `--output`, producing [development](raw/ai-mock-dev.json), [validation](raw/ai-mock-validation.json) and [test](raw/ai-mock-test.json) reports. New output names preserve existing evidence. The runner deliberately exposes mock mode only; a live experiment requires explicit spend authorization, current provider/model/pricing verification, the reservation path, and a separately frozen live model configuration. No GPU/cloud prerequisite exists for this mock workflow.

For teaching: PostgreSQL queues separate request latency from external provider latency; leases/fences separate durable intent from a worker's temporary authority; idempotent acceptance separates a proposal from a command; grouped splits and denominators keep measured model behavior separate from pipeline correctness. Read `ai/worker.py`, `ai/accept.py`, `evals/data/check.py` and `evals/score/metrics.py`. Interview discussion: why unknown cost consumes a conservative reservation, why a valid JSON response can still be semantically wrong, and why a high synthetic mock score cannot establish real model quality. Agent assistance and human-review status must remain explicit when presenting this work.
