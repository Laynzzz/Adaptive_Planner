"""One expendable CPU solve; no database session crosses this process boundary."""

import sys
from pathlib import Path

from planner.domain.contracts import InputSnapshot
from planner.ml.router import solve_routed
from planner.observability.routing import write_route


def main():
    snapshot = InputSnapshot.model_validate_json(Path(sys.argv[1]).read_text(encoding="utf-8"))
    candidate = solve_routed(
        snapshot,
        budget_ms=2000,
        seed=0,
        observe=lambda event: write_route(Path(sys.argv[2]), event),
    )
    Path(sys.argv[2]).write_text(
        candidate.model_dump_json(exclude_computed_fields=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
