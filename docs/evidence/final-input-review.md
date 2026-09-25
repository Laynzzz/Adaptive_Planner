# Final input and evaluation review

Reviewed the timezone preview/apply domain and API, TaskEditor, Commitments, availability removal, original-time endpoints/display, and `ml-experiment.md` against the frozen corrected evaluation. Review date: 2026-09-25. No model selection, frozen measurements or evaluation outputs were changed.

## Finding and authorized correction

**P1 — stale commitment drafts could overwrite concurrent edits.** The editor preserved uncontrolled draft fields while its PATCH command read the latest React Query revision. A refetch from revision 4 to 5 therefore submitted an older draft with revision 5 instead of triggering a stale-revision conflict. The interleaving component regression reproduced the wrong revision; the corrected editor captures event title, planning revision and timezone when opened. Refetch and conflict retries retain that capture and the command key. Closing/reopening explicitly loads the current values/revision. Successful save closes the draft. Direct remove actions continue to use their current event snapshot.

Evidence: [red](raw/commitment-edit-revision-red.txt), [green](raw/commitment-edit-revision-green.txt). The final test also verifies explicit close/reopen picks up the new title and revision. Five focused frontend files passed **10 tests** ([output](raw/final-input-component-review.txt)); frontend typecheck passed. Timezone and planning API integration checks passed **5 tests** using the real local OIDC provider and isolated PostgreSQL ([output](raw/final-timezone-api-review.txt)).

## Other reviewed behavior

No additional actionable defect was found in this bounded review. Timezone preview reads a consistent database snapshot, binds its hash to owner/revision and requires explicit confirmation. Applying the reviewed change preserves existing absolute timestamps, updates DATE civil boundaries and rolls back prohibited weekday/protected-work conflicts. Availability deletion sends the retained windows together with their own revision. Original-time endpoints apply owner predicates to both their parent resource and snapshot. TaskEditor retains the revision captured on opening.

This is a code and focused-test review, not a new claim of exhaustive browser or concurrency coverage. The root task separately owns full browser/integration verification.

## Corrected ML report reconciliation

The selection file still hashes to `4f7b0e0396150d8f1b2d6e4590b33131979f3ade97780b5493a7707f9bb4b35f`; the test artifact remains `9e121946bae7ce9814871b698c2065717b5f026a059baf0ab24cc281ad9bfe0b`. The corrected evaluation hashes to `855cf0317aecfa068ab86a807273e3ba5cbcb3336b1f230fc0ba841e6800171f`. Reported completion counts, latency comparisons, quality tail, uncertainty interval, all-negative known test labels and denied deployment agree with that corrected artifact.

The scheduler report's obsolete insufficient-paired-evidence sentence now explicitly identifies the original `cp_sat`/`cold_cp_sat` adapter defect and links the audited corrected report. The final six failed gates are `REFERENCE_COMPLETION_LOSS`, `TAIL_QUALITY_LOSS`, `ALWAYS_CP_P95_GAIN`, `SIMPLE_P95_GAIN`, `LATENCY_UNCERTAINTY` and `MEASUREMENT_SUPERVISION_LIMIT`. The correction does not change the selected model, threshold, inference results, solvers or original measurements.
