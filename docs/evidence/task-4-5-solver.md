# Solver evidence — Tasks 4 and 5

Environment: Windows, Python 3.12, dependencies frozen in `uv.lock`, 2026-09-25.
All fixtures are synthetic. Commands run in the implementation worktree using
`.tools/bin/uv.exe run` (the documented equivalent is `uv run`).

## Task 4

The independent validator imports no scheduling predicates. It recomputes owners,
interval/grid consistency, release/deadline bounds, workload, dependencies,
protected identity, availability, busy intervals, and overlap. Greedy uses earliest
eligible windows in topological/deadline/priority/release/ID order. A heuristic
failure returns UNKNOWN and violations, never an infeasibility proof.

Objective v1 freezes weights 30/25/20/15/10. Each component is floored at precision
1/10,000; completion positions are first floored per task, then priority averaged.
All zero denominators yield zero. Fragmentation compares block count with
ceil(allocated/max length) (one for unsplittable work), divided by allocated slots
minus that minimum. Disruption compares task/slot occupancy, double weighted for
the next 24 hours; identities do not affect this score. Only future unlocked
reference work counts. These preferences do not measure human productivity.

Command: `uv run pytest tests/unit/test_validator.py tests/unit/test_greedy.py
tests/unit/test_objective.py tests/property/test_schedule_invariants.py -q
--hypothesis-show-statistics`.

- Initial red: 19 missing-module failures in [raw/task-4-red.txt](raw/task-4-red.txt).
- Green: 19 tests, including exactly 1,000 generated examples, in
  [raw/task-4-green.txt](raw/task-4-green.txt).
- Deliberately disabling ownership and overlap reports separately makes their
  negative tests fail; source restored and green rerun. Evidence:
  [raw/task-4-mutations.txt](raw/task-4-mutations.txt).
- The first intermediate run found a test helper argument collision and only
  960 finite generated combinations. Both corrected before the recorded green.

These are local synthetic invariant checks, not a production capacity claim.

## Task 5

The interval model encodes required in-horizon effort, optional later work,
release/deadline bounds, all availability/busy intervals, segment ordering and
lengths, final-short rules, completion-gated precedence, and exact protected
blocks. It minimizes the same five bounded integer components as the reference
scorer. A validated greedy schedule provides interval hints. Every CP result is
checked by the independent validator before return. UNKNOWN and MODEL_INVALID
may return a validated GREEDY_FALLBACK; the original CP reason stays in metadata.
If no valid fallback exists, the result stays unresolved with no proposed blocks.
INFEASIBLE is reserved for a necessary-condition proof or the solver's proof.

The tiny reference enumerates ordered interval subsets without reusing CP model
predicates or validator feasibility logic. The oracle limit is eight slots and
three active tasks; production CP has no such limit. Fixtures and hand proofs are
in [../../tests/fixtures/solver/README.md](../../tests/fixtures/solver/README.md).

Command: `uv run pytest tests/unit/test_validator.py tests/unit/test_greedy.py
tests/unit/test_objective.py tests/unit/test_cp_sat.py tests/unit/test_diagnostics.py
tests/property/test_schedule_invariants.py -q --hypothesis-show-statistics`.

- Initial CP/diagnostic red: 11 failures from absent modules, preserved in
  [raw/task-5-red.txt](raw/task-5-red.txt).
- Green: 36 tests, 1,000 invariant examples and 100 independent tiny exhaustive
  comparisons, preserved in [raw/task-5-green.txt](raw/task-5-green.txt).
- Controlled solver adapters test timeout UNKNOWN, unresolved versus fallback,
  and MODEL_INVALID without relying on timing luck. Other tests cover 13 required
  blocks (no arbitrary per-task block cap), protected in-progress short work,
  optional predecessor gating, preferences and reference-plan disruption.
- Ruff check and format pass on solver code, owned tests and tiny reference.

Command: `uv run python -m benchmarks.tiny_reference`. Raw environment, fixture
SHA-256 hashes and results: [raw/task-5-size-smoke.jsonl](raw/task-5-size-smoke.jsonl).
Python 3.12.14, OR-Tools 9.15.6755, Windows 11, Intel family 6 model 183,
one CP search worker, seed 7, 2,000 ms search budget. One synthetic run per size,
all tasks request four slots with min/max block length 2/4 over 1,344 free slots.

| Tasks | Variables | Constraints | Build ms | Full pipeline ms | Result |
| --- | --- | --- | --- | --- | --- |
| 20 | 389 | 689 | 9.56 | 2012.17 | FEASIBLE, CP_SAT, valid |
| 50 | 959 | 1709 | 19.65 | 2024.72 | FEASIBLE, CP_SAT, valid |
| 100 | 1909 | 3409 | 44.46 | 2062.85 | FEASIBLE, CP_SAT, valid |
| 200 | 3809 | 6809 | 126.34 | 2150.34 | FEASIBLE, CP_SAT, valid |

None of these size-smoke runs proved optimality. They are not latency percentiles,
load tests or an across-instance performance guarantee. The search cap excludes
model construction; Task 6's worker must enforce the separate five-second process
wall limit. Protected/fixed/window counts and small block minima increase model
size. Interval count grows with sum(min(requested, available)/minimum block),
plus at most one final short segment per task. Objective overlap terms additionally
grow with preferred/reference windows.

Explicit model resource limits reject the entire input with MODEL_INVALID /
MODEL_RESOURCE_LIMIT instead of silently truncating block choices: horizon at
most 1,440 slots, total requested effort at most 1,000,000 slots, estimated optional
intervals at most 20,000, estimated objective overlap terms at most 100,000.
The horizon bound accommodates the normalized 14-day DST envelope. These are
conservative implementation bounds, not guarantees that every accepted model
finishes within five seconds. A regression case with 30 optional 1,000-slot tasks
first returned a validated fallback after 6.27 seconds before this guard; it now
returns an explicit resource error before model construction.

Diagnostics name necessary constraints and provide numeric facts; no minimal or
unique conflict-set claim is made. Bounded conflict-set extraction is not used.

## Learning handoff

Entry points: `solver/validator.py` demonstrates a trust boundary independent of
the optimization implementation; `solver/cp_sat.py` demonstrates optional interval
variables and hard completion flags; `benchmarks/tiny_reference.py` demonstrates
why exhaustive tiny search can catch model mistakes independently of production
constraint code. Python/OR-Tools run in the worker, not the browser.

Interview discussion: why greedy failure is not infeasibility; why a solver
timeout needs a validated fallback; why objective quality expresses a chosen
preference policy rather than observed productivity. Explain the trade-off between
15-minute finite modeling, integer score precision, exhaustive tiny proofs and
bounded large-instance search. Optional exercise: alter a tiny task release time,
predict the resulting feasible schedules, then verify using the enumeration.

## Independent review correction

The backend reviewer's additional tiny search found an omitted CP constraint for
unsplittable work shorter than its declared minimum when a short final block is
not allowed. The validator correctly rejected that CP result, but this converted
a required infeasible instance into MODEL_INVALID and made an optional instance
use fallback unnecessarily. The model now applies the minimum to unsplittable
work as well. Required and optional regressions failed first (2 failures), then
passed with the full solver suite. Raw evidence:
`raw/task-5-review-minimum-red.txt` and `raw/task-5-review-minimum-green.txt`.

The same independent review found that prior-candidate integer slots retained
the previous snapshot's UTC-midnight origin. After midnight, unchanged absolute
work was scored as displaced and CP could optimize toward the wrong intervals.
Both objective consumers now derive reference slots from prior block UTC
start/end against the current snapshot origin, preserving the immutable prior
candidate. A real-normalization next-day fixture first failed with disruption
1 instead of 0 and CP moving the block; after correction both preserve the
reference interval. Raw evidence: `raw/task-5-review-origin-red.txt` and
`raw/task-5-review-origin-green.txt`. Full solver suite: 40 tests, 1,000 generated
invariants and 100 exhaustive tiny comparisons after both corrections.
