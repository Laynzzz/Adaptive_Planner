"""Local development commands; no synthetic authentication bypass."""

import argparse

import uvicorn

from planner.db.session import create_db_engine, database_is_ready, migration_heads
from planner.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive Planner service")
    parser.add_argument("command", choices=["serve", "check-ready", "seed-demo"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("planner.app:create_app", factory=True, host=args.host, port=args.port)
        return 0
    if args.command == "seed-demo":
        parser.error(
            "seed-demo requires the Task 3 identity/task schema; it is not implemented yet"
        )
    engine = create_db_engine(Settings())
    try:
        ready = database_is_ready(engine, migration_heads())
    finally:
        engine.dispose()
    print("ready" if ready else "not_ready")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
