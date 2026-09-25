# Task 2 — domain contracts and time semantics

Status: local domain increment verified on 2026-09-25. This is not the R1 release gate.
Base revision before this increment: `867dc48`. The commit containing this report identifies the implementation revision.

## Implemented boundaries

- Frozen Pydantic contracts for tasks, snapshots, blocks, candidates, violations, proposals, extraction proposals, finite ordered features, score, plan diff, model manifest and routing decisions. Nested facts and policy parameters are immutable scalar mappings, including their empty defaults.
- `normalize_time_inputs(raw, now)` consumes explicit instants and a fixed aware clock. UTC midnight of that clock's UTC date is the explicit `slot_origin`. Horizon start is the first available unoccupied slot; horizon end is midnight fourteen local calendar dates later. Availability and busy intervals are clipped at the clock cutoff and horizon end, independently of the first available slot.
- Availability rounds inward, busy intervals outward, releases/now upward and deadline feasibility downward. Date-only deadlines use the following local midnight. Remaining minutes stay unrounded; required slots are derived. Raw forms cannot supply derived workload or deadline/release fields.
- Missing DST wall times fail explicitly; repeated-hour inputs require a fold or an explicit offset. Calendar horizons are elapsed UTC instants rather than 96 slots per local date. Original local interval input, IANA zone, optional fold and rounding losses remain in the serialized snapshot.
- Timezone preview is detached and preserves fixed event/timestamp instants while reinterpreting date-only intent. This function grants no activation authority; confirmation and persistence belong to commands.
- Task validation reports cycles, missing or cross-owner dependencies, cancelled predecessors, past deadlines, owner mismatches, over-reserved work and fixed/protected conflicts. DONE dependencies are satisfied. Future portions of declared in-progress intervals count toward remaining work; completed historical blocks are excluded.
- Explicit observed-work transitions require a new estimate or completion and preserve the input object. Persisting observations/corrections append-only remains a later command/persistence responsibility.
- Fixture builders do not repair overridden timestamps, owners, revisions, hashes or slot ranges. Their fixed origin and clock are documented in `tests/fixtures/builders.py`.

## Verification and failures retained

Windows local checkout; uv-managed Python 3.12.14; pytest 9.1.1; Pydantic 2.13.5; tzdata 2026.4; Ruff 0.16.9. Dependency pins live in `uv.lock`.

Commands from the repository root:

```powershell
.\.tools\bin\uv.exe run pytest tests/unit/test_time_rules.py tests/unit/test_task_rules.py tests/unit/test_contracts.py -q
.\.tools\bin\uv.exe run ruff check services/planner/src/planner/domain tests/unit/test_time_rules.py tests/unit/test_task_rules.py tests/unit/test_contracts.py tests/fixtures/builders.py
```

Final result: **29 passed in 0.27 seconds**, and scoped Ruff **All checks passed**. These are deterministic local unit checks, not API, persistence, browser, live-provider or capacity evidence.

Observed test-first sequence:

1. Initial collection failed because the time module was absent. Minimal unimplemented boundaries then produced **10 failing time tests**, each raising `NotImplementedError`.
2. Time implementation produced **10 passed / 6 failed**; the six task tests failed at the unimplemented task boundaries.
3. Task implementation and initial contract checks produced **23 passed**. Initial constructor/contract checks were written before implementation but were first executed with their implementation present; those individual checks do not have a separately recorded red run.
4. Added regression checks yielded **4 failed / 18 passed**: absent original local input metadata, silently rounded locks, missing expected-end error handling and mutable empty facts. Their corrections produced **28 passed** across the domain suite.
5. A raw-form forged deadline slot check failed because injection was accepted. Rejecting derived fields produced the final **29 passed**.
6. Ruff initially reported formatting/import issues. Its formatter and scoped import fixes were followed by the clean result above.

The fixture manifest is `tests/fixtures/time/manifest.json`. The hand-authored busy fixture SHA-256 is `3BA6AE942007C097B2012BAE65AD945455CD78906036F6686A5074B5CADECA12`.

## Integration notes and limits

- Snapshot/candidate output includes computed read-only fields. Persist/reload contracts with `model_dump(mode="json", exclude_computed_fields=True)` or the corresponding `model_dump_json` flag; do not feed API presentation-only computed fields back as editable task input.
- `validate_tasks` checks planning inputs; candidate allocation, release/deadline, exact lock preservation, ownership and dependency completion still require the independent solver validator in Task 4.
- Off-grid locked blocks are rejected with `LOCK_NOT_GRID_ALIGNED` rather than silently moving their absolute instants. Explicit in-progress reservations are bounded; their retained future grid portion includes `original_start` for inspection.
- No API mutation, append-only database log, timezone confirmation UI, live calendar, solver or model training is claimed here.

## Learning handoff

The key distinction is elapsed time versus local intent: actual UTC instants avoid duplicated or missing solver slots, while the original local fields explain what the person entered. Conservative rounding can reject a schedule that would fit in continuous time, so grid infeasibility must not be described as universal impossibility. Read `domain/time_rules.py` with the fixture manifest, then `domain/contracts.py` and `domain/task_rules.py`.

Interview prompt: why not subtract 15 observed minutes from a 31-minute estimate automatically? Observed effort and a remaining estimate measure different things; requiring a new explicit estimate avoids pretending elapsed work proves progress or completion.
