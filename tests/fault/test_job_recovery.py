"""Bounded process and recovery fault paths without mocking the solver boundary."""

import sys
import time
from datetime import timedelta

from sqlalchemy.orm import Session

from planner.jobs.coalescing import enqueue
from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import fail_attempt
from tests.integration.test_jobs import NOW, seed_owner
from tests.integration.test_jobs import job_engine as job_engine


def test_transient_retries_are_capped_at_five_attempts(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    now = NOW
    for attempt in range(5):
        claim = claim_next(job_engine, now=now)
        assert claim is not None
        result = fail_attempt(job_engine, claim, now=now, reason_code="CHILD_CRASH", retryable=True)
        assert result.state == ("FAILED" if attempt == 4 else "RETRY_WAIT")
        now += timedelta(seconds=61)
    assert claim_next(job_engine, now=now) is None


def test_permanent_failure_is_not_retried(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    assert (
        fail_attempt(job_engine, claim, now=NOW, reason_code="INVALID_INPUT", retryable=False).state
        == "FAILED"
    )
    assert claim_next(job_engine, now=NOW + timedelta(seconds=61)) is None


def test_running_child_is_terminated_when_input_becomes_obsolete():
    from planner.jobs import subprocesses

    assert hasattr(subprocesses, "run_process")
    start = time.monotonic()
    result = subprocesses.run_process(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        timeout_seconds=5,
        is_cancelled=lambda: time.monotonic() - start > 0.2,
    )
    assert result.reason_code == "SUPERSEDED"
    assert result.elapsed_seconds < 1.2
    assert result.returncode is not None


def test_hung_child_is_terminated_at_wall_budget():
    from planner.jobs import subprocesses

    assert hasattr(subprocesses, "run_process")
    result = subprocesses.run_process(
        [sys.executable, "-c", "import time; time.sleep(30)"], timeout_seconds=0.3
    )
    assert result.reason_code == "WALL_TIMEOUT"
    assert result.elapsed_seconds < 1.2
    assert result.returncode is not None


def test_reconciliation_restores_orphaned_retry_demand(job_engine):
    from sqlalchemy import delete

    from planner.db.models import PendingReplan
    from planner.jobs.leases import reconcile_expired

    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    fail_attempt(job_engine, claim, now=NOW, reason_code="CHILD_CRASH", retryable=True)
    with Session(job_engine) as db, db.begin():
        db.execute(delete(PendingReplan).where(PendingReplan.owner_id == owner))
    reconcile_expired(job_engine, now=NOW + timedelta(seconds=61))
    assert claim_next(job_engine, now=NOW + timedelta(seconds=61)) is not None


def test_real_solver_process_returns_a_validated_candidate():
    from planner.jobs.subprocesses import run_solver
    from planner.solver.validator import validate_candidate
    from tests.fixtures.builders import snapshot

    source = snapshot()
    result = run_solver(source)
    assert result.reason_code is None
    assert result.candidate is not None
    assert validate_candidate(source, result.candidate) == []


def test_wall_timeout_uses_only_an_independently_validated_greedy_fallback():
    from planner.jobs.subprocesses import run_solver
    from planner.solver.validator import validate_candidate
    from tests.fixtures.builders import snapshot

    source = snapshot()
    result = run_solver(source, timeout_seconds=0.001)
    assert result.candidate is not None
    assert result.candidate.source_policy == "GREEDY_FALLBACK"
    assert result.candidate.solver_metadata.reason_code == "WALL_TIMEOUT"
    assert validate_candidate(source, result.candidate) == []


def test_slow_state_check_cannot_extend_the_child_wall_deadline(tmp_path):
    from planner.jobs.subprocesses import run_process

    marker = tmp_path / "outlived-budget.txt"

    def slow_check():
        time.sleep(1)
        return False

    result = run_process(
        [
            sys.executable,
            "-c",
            "import time,pathlib,sys; time.sleep(0.7); "
            'pathlib.Path(sys.argv[1]).write_text("late")',
            str(marker),
        ],
        timeout_seconds=0.2,
        is_cancelled=slow_check,
    )
    assert result.reason_code == "WALL_TIMEOUT"
    assert not marker.exists()


def test_worker_shutdown_stops_claims_and_releases_inflight_lease(job_engine):
    import threading

    from sqlalchemy import select

    from planner.db.job_models import Job
    from planner.jobs import worker

    assert hasattr(worker, "serve")
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    stop = threading.Event()
    thread = threading.Thread(
        target=worker.serve, args=(job_engine, stop), kwargs={"clock": lambda: NOW}
    )
    thread.start()
    try:
        deadline = time.monotonic() + 4
        running = False
        while time.monotonic() < deadline:
            with Session(job_engine) as db:
                running = db.scalar(select(Job.id).where(Job.state == "RUNNING")) is not None
            if running:
                break
            time.sleep(0.01)
        assert running
    finally:
        stop.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
    with Session(job_engine) as db:
        assert db.scalar(select(Job.id).where(Job.state == "RUNNING")) is None
