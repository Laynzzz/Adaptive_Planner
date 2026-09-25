"""Local development commands; no synthetic authentication bypass."""

import argparse

import uvicorn

from planner.db.demo import seed_demo
from planner.db.session import create_db_engine, database_is_ready, migration_heads
from planner.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive Planner service")
    parser.add_argument("command", choices=["serve", "check-ready", "seed-demo", "prune-traces"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run(
            "planner.app:create_app", factory=True, host=args.host, port=args.port, access_log=False
        )
        return 0
    engine = create_db_engine(Settings())
    try:
        if args.command == "prune-traces":
            from datetime import UTC, datetime

            from planner.observability.database import retain_recent_context

            count = retain_recent_context(engine, now=datetime.now(UTC))
            print(f"Removed {count} diagnostic trace links older than seven days.")
            return 0
        if args.command == "seed-demo":
            try:
                count = seed_demo(engine, Settings())
            except ValueError as error:
                parser.error(str(error))
            print(f"Seeded {count} demo workspaces; existing demo tasks were preserved.")
            return 0
        ready = database_is_ready(engine, migration_heads())
    finally:
        engine.dispose()
    print("ready" if ready else "not_ready")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
