import json
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.db.models import PendingReplan, PlanningState
from planner.jobs.coalescing import enqueue
from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import finalize
from planner.solver.greedy import greedy_schedule
from tests.integration.test_jobs import NOW, seed_owner
from tests.integration.test_jobs import job_engine as job_engine


def test_edit_storm_preserves_oldest_age_and_dispatches_by_two_seconds(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW)
    assert claim_next(job_engine, now=NOW + timedelta(milliseconds=200)) is None
    for i in range(1, 20):
        enqueue(job_engine, owner, now=NOW + timedelta(milliseconds=100 * i))
    with Session(job_engine) as db:
        assert db.get(PendingReplan, owner).enqueued_at == NOW
    assert claim_next(job_engine, now=NOW + timedelta(seconds=2)) is not None


def test_ten_queued_owners_receive_a_round_with_two_active_slots(job_engine):
    owners = [seed_owner(job_engine, index=i) for i in range(10)]
    for owner in owners:
        enqueue(job_engine, owner, now=NOW, explicit=True)
    sequence = []
    durations = []
    for round_index in range(5):
        now = NOW + timedelta(seconds=round_index)
        active = [claim_next(job_engine, now=now), claim_next(job_engine, now=now)]
        assert all(active)
        assert claim_next(job_engine, now=now) is None
        sequence.extend(claim.owner_id for claim in active)
        for claim in active:
            started = time.perf_counter()
            finalize(job_engine, claim, greedy_schedule(claim.snapshot), now=now)
            durations.append(round((time.perf_counter() - started) * 1000, 3))
            enqueue(job_engine, claim.owner_id, now=now, explicit=True)
    assert len(set(sequence)) == 10
    assert set(sequence) == set(owners)
    print(
        json.dumps(
            {
                "owner_dispatch_sequence": [owners.index(owner) for owner in sequence],
                "greedy_and_result_transaction_ms": durations,
                "solve_slots": 2,
            }
        )
    )


def test_owner_never_has_two_active_solves(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    assert claim_next(job_engine, now=NOW)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    assert claim_next(job_engine, now=NOW) is None


def test_dispatch_skips_owner_with_an_in_progress_input_transaction(job_engine):
    from concurrent.futures import ThreadPoolExecutor

    first = seed_owner(job_engine)
    other = seed_owner(job_engine)
    enqueue(job_engine, first, now=NOW, explicit=True)
    enqueue(job_engine, other, now=NOW + timedelta(milliseconds=1), explicit=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with Session(job_engine) as db, db.begin():
            db.scalar(
                select(PlanningState).where(PlanningState.owner_id == first).with_for_update()
            )
            future = pool.submit(claim_next, job_engine, now=NOW + timedelta(seconds=1))
            claim = future.result(timeout=1)
        assert claim.owner_id == other


def test_dispatch_state_initialization_cannot_block_other_owners(job_engine):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import delete

    from planner.db.job_models import OwnerDispatchState

    first = seed_owner(job_engine)
    other = seed_owner(job_engine)
    enqueue(job_engine, first, now=NOW, explicit=True)
    enqueue(job_engine, other, now=NOW, explicit=True)
    with Session(job_engine) as db, db.begin():
        db.execute(delete(OwnerDispatchState).where(OwnerDispatchState.owner_id == first))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with Session(job_engine) as db, db.begin():
            db.scalar(
                select(PlanningState).where(PlanningState.owner_id == first).with_for_update()
            )
            db.add(OwnerDispatchState(owner_id=first))
            db.flush()
            result = pool.submit(claim_next, job_engine, now=NOW)
            claim = result.result(timeout=1)
        assert claim.owner_id == other


def test_new_revision_does_not_inherit_an_old_attempt_retry_delay(job_engine):
    from planner.db.job_models import Job
    from planner.jobs.handlers import fail_attempt

    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    for index in range(3):
        at = NOW + timedelta(seconds=61 * index)
        claim = claim_next(job_engine, now=at)
        fail_attempt(job_engine, claim, now=at, reason_code="CHILD_CRASH", retryable=True)
    edited = at + timedelta(milliseconds=100)
    with Session(job_engine) as db, db.begin():
        db.get(PlanningState, owner).revision = 1
        pending = db.get(PendingReplan, owner)
        pending.desired_revision = 1
        pending.updated_at = edited
    fresh = claim_next(job_engine, now=edited + timedelta(seconds=2))
    assert fresh is not None
    assert fresh.snapshot.planning_revision == 1
    with Session(job_engine) as db:
        assert db.get(Job, fresh.job_id).attempts == 1
