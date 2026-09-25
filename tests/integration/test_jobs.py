"""Durable worker behavior against isolated, real PostgreSQL transactions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.db.models import Availability, Identity, PlanningState, Task
from planner.domain.plans import activate_proposal
from planner.jobs.coalescing import enqueue
from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import finalize
from planner.jobs.leases import heartbeat, reconcile_expired
from planner.solver.greedy import greedy_schedule

NOW = datetime(2026, 9, 25, 9, tzinfo=UTC)


def seed_owner(engine, index=0):
    owner = uuid4()
    with Session(engine) as db, db.begin():
        db.add(
            Identity(
                id=owner,
                issuer="https://fixture.invalid",
                subject=str(owner),
                name=f"Owner {index}",
            )
        )
        db.flush()
        db.add(PlanningState(owner_id=owner, revision=0))
        db.add(
            Task(
                id=uuid4(),
                owner_id=owner,
                title="Draft",
                remaining_minutes=60,
                priority=3,
                state="TODO",
                details={"deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T17:00:00Z"}},
            )
        )
        db.add(
            Availability(
                owner_id=owner, windows=[{"start": "2026-09-25T09:00Z", "end": "2026-09-25T17:00Z"}]
            )
        )
    return owner


@pytest.fixture
def job_engine(migrated_database_url):
    from sqlalchemy import create_engine

    engine = create_engine(migrated_database_url)
    yield engine
    engine.dispose()


def test_explicit_generate_has_stable_id_and_captures_immutable_snapshot(job_engine):
    owner = seed_owner(job_engine)
    job_id = enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    assert claim.job_id == job_id
    assert claim.snapshot.tasks[0].remaining_minutes == 60
    with Session(job_engine) as db, db.begin():
        task = db.scalar(select(Task).where(Task.owner_id == owner))
        task.remaining_minutes = 120
    assert claim.snapshot.tasks[0].remaining_minutes == 60


def test_stale_result_is_superseded_and_cannot_activate(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    result = greedy_schedule(claim.snapshot)
    with Session(job_engine) as db, db.begin():
        db.get(PlanningState, owner).revision = 1
    enqueue(job_engine, owner, now=NOW + timedelta(seconds=1))
    finished = finalize(job_engine, claim, result, now=NOW + timedelta(seconds=1))
    assert finished.state == "SUPERSEDED"
    assert finished.proposal_id is None


def test_valid_result_activation_is_atomic_and_rejects_time_advance(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    finished = finalize(job_engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    assert finished.state == "SUCCEEDED"
    accepted = activate_proposal(
        job_engine, owner, finished.proposal_id, expected_revision=0, now=NOW
    )
    assert accepted.code == "ACTIVATED"
    with Session(job_engine) as db:
        assert db.get(PlanningState, owner).active_proposal_id == finished.proposal_id
    late = activate_proposal(
        job_engine,
        owner,
        finished.proposal_id,
        expected_revision=0,
        now=NOW + timedelta(minutes=16),
    )
    assert late.code == "CURRENT_TIME_CONFLICT"


def test_invalid_candidate_is_never_a_current_proposal(job_engine):
    from planner.domain.contracts import Candidate

    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    invalid = Candidate(
        snapshot_hash=claim.snapshot.snapshot_hash,
        planning_revision=0,
        status="FEASIBLE",
        source_policy="FORGED",
    )
    finished = finalize(job_engine, claim, invalid, now=NOW)
    assert finished.state == "FAILED"
    assert finished.proposal_id is None


def test_foreign_owner_cannot_activate_or_reveal_proposal(job_engine):
    owner = seed_owner(job_engine)
    other = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    finished = finalize(job_engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    assert (
        activate_proposal(
            job_engine, other, finished.proposal_id, expected_revision=0, now=NOW
        ).code
        == "NOT_FOUND"
    )


def test_expired_lease_takeover_fences_old_worker_and_heartbeat(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    old = claim_next(job_engine, now=NOW)
    assert heartbeat(job_engine, old, now=NOW + timedelta(seconds=5))
    assert reconcile_expired(job_engine, now=NOW + timedelta(seconds=36)) == 1
    new = claim_next(job_engine, now=NOW + timedelta(seconds=36))
    assert new.job_id == old.job_id
    assert new.fencing_token > old.fencing_token
    assert not heartbeat(job_engine, old, now=NOW + timedelta(seconds=37))
    assert (
        finalize(
            job_engine, old, greedy_schedule(old.snapshot), now=NOW + timedelta(seconds=37)
        ).state
        == "FENCED"
    )


def test_finalize_is_idempotent_after_result_commit_before_ack(job_engine):
    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    candidate = greedy_schedule(claim.snapshot)
    first = finalize(job_engine, claim, candidate, now=NOW)
    second = finalize(job_engine, claim, candidate, now=NOW)
    assert first.proposal_id == second.proposal_id
    assert first.state == second.state == "SUCCEEDED"


def test_active_pointer_cannot_cross_owner_even_below_api(job_engine):
    from sqlalchemy.exc import IntegrityError

    owner = seed_owner(job_engine)
    other = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    result = finalize(job_engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    with pytest.raises(IntegrityError):
        with Session(job_engine) as db, db.begin():
            db.get(PlanningState, other).active_proposal_id = result.proposal_id


def test_snapshot_and_candidate_payloads_are_immutable_in_storage(job_engine):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    result = finalize(job_engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    for statement in (
        "UPDATE immutable_snapshots SET payload = '{}'",
        "UPDATE proposals SET candidate = '{}' WHERE id = :id",
    ):
        with pytest.raises(DBAPIError):
            with job_engine.begin() as db:
                db.execute(text(statement), {"id": result.proposal_id})


def test_concurrent_dispatchers_respect_global_pool_limit(job_engine):
    from concurrent.futures import ThreadPoolExecutor

    for i in range(5):
        owner = seed_owner(job_engine, index=i)
        enqueue(job_engine, owner, now=NOW, explicit=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        claims = list(pool.map(lambda _: claim_next(job_engine, now=NOW), range(5)))
    assert sum(claim is not None for claim in claims) == 2


def test_selecting_new_proposal_does_not_leave_two_active_or_false_reactivation(job_engine):
    from planner.db.job_models import ProposalRecord

    owner = seed_owner(job_engine)
    selected = []
    for _ in range(2):
        enqueue(job_engine, owner, now=NOW, explicit=True)
        claim = claim_next(job_engine, now=NOW)
        result = finalize(job_engine, claim, greedy_schedule(claim.snapshot), now=NOW)
        assert (
            activate_proposal(
                job_engine, owner, result.proposal_id, expected_revision=0, now=NOW
            ).code
            == "ACTIVATED"
        )
        selected.append(result.proposal_id)
    with Session(job_engine) as db:
        assert list(
            db.scalars(
                select(ProposalRecord.id).where(
                    ProposalRecord.owner_id == owner, ProposalRecord.state == "ACTIVE"
                )
            )
        ) == [selected[1]]
    assert (
        activate_proposal(job_engine, owner, selected[0], expected_revision=0, now=NOW).code
        == "STALE_REVISION"
    )


def test_finalization_validates_persisted_snapshot_not_worker_supplied_copy(job_engine):
    from dataclasses import replace

    from planner.domain.contracts import Candidate

    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    forged = replace(claim, snapshot=claim.snapshot.model_copy(update={"tasks": ()}))
    empty = Candidate(
        snapshot_hash=claim.snapshot.snapshot_hash,
        planning_revision=0,
        status="FEASIBLE",
        source_policy="FORGED",
    )
    assert finalize(job_engine, forged, empty, now=NOW).state == "FAILED"


@pytest.mark.parametrize("status", ["INFEASIBLE", "UNKNOWN", "MODEL_INVALID"])
def test_nonsolution_status_and_diagnostics_are_retained(job_engine, status):
    from planner.db.job_models import Job
    from planner.domain.contracts import Candidate, Violation

    owner = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    result = Candidate(
        snapshot_hash=claim.snapshot.snapshot_hash,
        planning_revision=0,
        status=status,
        source_policy="CP_SAT",
        constraint_report=(Violation(code="CAPACITY_BEFORE_DEADLINE"),),
    )
    finished = finalize(job_engine, claim, result, now=NOW)
    assert finished.reason_code == status
    with Session(job_engine) as db:
        saved = Candidate.model_validate(db.get(Job, claim.job_id).result)
    assert [v.code for v in saved.constraint_report] == ["CAPACITY_BEFORE_DEADLINE"]


def test_job_result_link_and_persisted_blocks_cannot_bypass_owner_immutability(job_engine):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    owner = seed_owner(job_engine)
    other = seed_owner(job_engine)
    enqueue(job_engine, owner, now=NOW, explicit=True)
    claim = claim_next(job_engine, now=NOW)
    result = finalize(job_engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    other_job = enqueue(job_engine, other, now=NOW, explicit=True)
    for sql in (
        "UPDATE jobs SET proposal_id=:proposal WHERE id=:job",
        "UPDATE proposal_blocks SET locked=true WHERE proposal_id=:proposal",
    ):
        with pytest.raises(DBAPIError):
            with job_engine.begin() as db:
                db.execute(text(sql), {"job": other_job, "proposal": result.proposal_id})
