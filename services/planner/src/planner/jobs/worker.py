"""Local worker: two bounded solve slots, no CPU solver in the HTTP process."""

import logging
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from planner.db.session import create_db_engine
from planner.domain.contracts import Candidate
from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import fail_attempt, finalize
from planner.jobs.leases import heartbeat, is_obsolete, reconcile_expired
from planner.jobs.subprocesses import run_solver
from planner.observability.runtime import span, traced_work
from planner.settings import Settings

SOLVE_POOL_SIZE = 2
# Reserved for the separate provider adapters; R1 starts no I/O workers.
IO_POOL_SIZE = 4


def utc_now():
    return datetime.now(UTC)


@traced_work("solve")
def work_claim(engine, claim, stop, clock=utc_now):
    result = run_solver(
        claim.snapshot,
        is_cancelled=lambda: stop.is_set() or is_obsolete(engine, claim),
        on_heartbeat=lambda: heartbeat(engine, claim, now=clock()),
    )
    if result.candidate is not None:
        with span(
            "job.result",
            solver_status=result.candidate.status,
            reason_code=result.candidate.solver_metadata.reason_code,
        ):
            return finalize(engine, claim, result.candidate, now=clock())
    if result.reason_code == "SUPERSEDED" and not stop.is_set():
        empty = Candidate(
            snapshot_hash=claim.snapshot.snapshot_hash,
            planning_revision=claim.snapshot.planning_revision,
            status="UNKNOWN",
            source_policy="CANCELLED",
        )
        return finalize(engine, claim, empty, now=clock())
    return fail_attempt(
        engine,
        claim,
        now=clock(),
        reason_code=result.reason_code or "CHILD_CRASH",
        retryable=result.reason_code != "INVALID_CHILD_RESULT",
    )


def serve(engine, stop, *, clock=utc_now):
    futures = set()
    try:
        with ThreadPoolExecutor(max_workers=SOLVE_POOL_SIZE) as pool:
            while not stop.is_set():
                for future in tuple(futures):
                    if future.done():
                        try:
                            future.result()
                        except Exception as error:
                            # The durable lease reconciler recovers failed host work.
                            logging.error(
                                "Worker attempt interrupted; lease recovery will retry (%s)",
                                type(error).__name__,
                            )
                        futures.remove(future)
                reconcile_expired(engine, now=clock())
                while len(futures) < SOLVE_POOL_SIZE and not stop.is_set():
                    claim = claim_next(engine, now=clock(), pool_size=SOLVE_POOL_SIZE)
                    if claim is None:
                        break
                    futures.add(pool.submit(work_claim, engine, claim, stop, clock))
                stop.wait(0.1)
    finally:
        stop.set()


def main():
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    engine = create_db_engine(Settings())
    from planner.observability.runtime import get_telemetry

    get_telemetry().observe_database(engine)
    try:
        serve(engine, stop)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
