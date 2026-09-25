# Tiny synthetic proofs

All intervals use 15-minute slots after UTC midnight 2026-09-25. The JSON files
contain complete immutable InputSnapshot payloads, with derived fields excluded.

`greedy_fails_but_feasible.json`: A needs two contiguous slots, release 2,
deadline 5. B needs three contiguous slots, release 0, deadline 6. Availability
is [0,6). Deadline-first greedy places A at [2,4), leaving no three-slot window
for B. B [0,3), A [3,5) is a feasible witness. The CP/reference scorer chooses
that earliest-completing witness; an exhausted greedy search is never a proof.

`capacity_infeasible.json`: two tasks each need four slots by slot 4. Only four
slots exist before slot 4. Eight required slots exceed four available slots,
which proves infeasibility of this normalized grid instance. It makes no claim
about a continuous-time model with different assumptions.

The enumeration oracle builds all ordered interval subsets within an eight-slot,
three-task limit and has a separate feasibility predicate. Tests compare both
solver feasibility and the full integer objective with that enumeration.
