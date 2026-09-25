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

These are local synthetic invariant checks, not a capacity or optimality claim.
Task 5 implementation and bounded measurements follow in the next commit.
