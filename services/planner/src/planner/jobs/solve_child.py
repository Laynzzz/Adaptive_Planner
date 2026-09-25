"""One expendable CPU solve; no database session crosses this process boundary."""

import sys
from pathlib import Path

from planner.domain.contracts import InputSnapshot
from planner.solver.cp_sat import solve_cp_sat


def main():
    snapshot = InputSnapshot.model_validate_json(Path(sys.argv[1]).read_text(encoding="utf-8"))
    candidate = solve_cp_sat(snapshot, budget_ms=2000, seed=0)
    Path(sys.argv[2]).write_text(
        candidate.model_dump_json(exclude_computed_fields=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
