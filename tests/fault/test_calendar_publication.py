"""Real durable state, synthetic remote faults; no live calendar credentials."""
# ruff: noqa: F811 -- imported pytest fixtures are deliberately injected by name.

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.db.calendar_models import (
    BlockEventMapping,
    CalendarConflict,
    CalendarConnection,
    CalendarWriteOperation,
)
from planner.db.models import PlanningState
from planner.domain.plans import activate_proposal
from planner.jobs.coalescing import enqueue
from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import finalize
from planner.solver.greedy import greedy_schedule
from tests.integration.test_calendar_sync import calendar_scenario, sync  # noqa: F401
from tests.integration.test_jobs import NOW


def activate(scenario):
    engine, owner, _ = scenario
    with Session(engine) as db:
        revision = db.get(PlanningState, owner).revision
    enqueue(engine, owner, now=NOW, explicit=True)
    claim = claim_next(engine, now=NOW)
    result = finalize(engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    assert (
        activate_proposal(
            engine, owner, result.proposal_id, expected_revision=revision, now=NOW
        ).code
        == "ACTIVATED"
    )
    return result.proposal_id


def publish(scenario):
    from planner.calendar.publish import publish_active

    engine, owner, provider = scenario
    return publish_active(engine, owner, provider, clock=lambda: NOW)


def test_timeout_after_remote_create_does_not_duplicate(calendar_scenario):
    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    provider.timeout_after_write = True
    assert publish(calendar_scenario).state == "PARTIAL"
    with Session(engine) as db:
        assert db.scalar(select(CalendarWriteOperation)).state == "UNCERTAIN"
    assert publish(calendar_scenario).state == "PUBLISHED"
    assert len(provider.events) == 1
    assert len(provider.writes) == 1
    with Session(engine) as db:
        assert db.scalar(select(BlockEventMapping)).state == "PUBLISHED"


def test_manual_move_becomes_locked_without_double_busy(calendar_scenario):
    from planner.calendar.sync import calendar_inputs

    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    sync(calendar_scenario)
    with Session(engine) as db:
        assert calendar_inputs(db, owner)[0] == []
        assert db.get(PlanningState, owner).revision == 0
    remote = next(iter(provider.events.values()))
    provider.put_external(
        {
            **remote,
            "start": {"dateTime": (NOW + timedelta(hours=2)).isoformat()},
            "end": {"dateTime": (NOW + timedelta(hours=3)).isoformat()},
        }
    )
    sync(calendar_scenario)
    with Session(engine) as db:
        busy, protected, _ = calendar_inputs(db, owner)
        assert busy == []
        assert len(protected) == 1 and protected[0]["locked"] is True
        assert protected[0]["start"] == (NOW + timedelta(hours=2)).isoformat()
        assert db.scalar(select(CalendarConflict)).reason == "MANUAL_EDIT"
        assert db.get(PlanningState, owner).revision == 1
    assert publish(calendar_scenario).state == "CONFLICT"
    assert len(provider.writes) == 1


def test_manual_deletion_is_never_automatically_recreated(calendar_scenario):
    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    remote = next(iter(provider.events.values()))
    provider.put_external({"id": remote["id"], "status": "cancelled"})
    sync(calendar_scenario)
    assert publish(calendar_scenario).state == "CONFLICT"
    assert len(provider.writes) == 1
    with Session(engine) as db:
        assert db.scalar(select(CalendarConflict)).reason == "MANUAL_DELETION"


def test_same_id_with_wrong_marker_is_a_conflict(calendar_scenario):
    from planner.calendar.reconcile import event_id
    from planner.db.job_models import ProposalBlock

    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    with Session(engine) as db:
        block = db.scalar(select(ProposalBlock))
    provider.put_external(
        {
            "id": event_id(owner, "synthetic", block.id),
            "start": {"dateTime": block.start.isoformat()},
            "end": {"dateTime": block.end.isoformat()},
        }
    )
    assert publish(calendar_scenario).state == "CONFLICT"
    assert provider.writes == []


def test_write_finishing_after_new_activation_is_obsolete_then_reconciles(calendar_scenario):
    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    provider.after_write = lambda: activate(calendar_scenario)
    assert publish(calendar_scenario).state == "PARTIAL"
    with Session(engine) as db:
        assert db.scalar(select(CalendarWriteOperation)).state == "OBSOLETE"
    assert publish(calendar_scenario).state == "PUBLISHED"
    assert len([e for e in provider.events.values() if e.get("status") != "cancelled"]) == 1


def test_lease_prevents_second_calendar_writer(calendar_scenario):
    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    provider.after_write = lambda: setattr(provider, "nested", publish(calendar_scenario).state)
    assert publish(calendar_scenario).state == "PUBLISHED"
    assert provider.nested == "BUSY"


def test_expired_auth_stops_publication(calendar_scenario):
    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    provider.authentication_required = True
    assert publish(calendar_scenario).state == "NEEDS_REAUTH"
    with Session(engine) as db:
        assert db.get(CalendarConnection, owner).state == "NEEDS_REAUTH"


def test_manual_description_edit_is_not_overwritten(calendar_scenario):
    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    remote = next(iter(provider.events.values()))
    provider.put_external({**remote, "description": "Manual note that must survive."})
    # A new active version must inspect the remote etag before modifying the resource.
    activate(calendar_scenario)
    assert publish(calendar_scenario).state == "CONFLICT"
    assert len(provider.writes) == 1
    assert next(iter(provider.events.values()))["description"].startswith("Manual note")


def test_manual_change_between_read_and_conditional_write_is_preserved(calendar_scenario):
    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    with Session(engine) as db, db.begin():
        from planner.db.models import Task

        db.scalar(select(Task)).title = "Changed title"
    activate(calendar_scenario)
    original = provider.update_event

    def racing_update(calendar_id, remote_id, payload, *, etag):
        provider.put_external(
            {
                **provider.events[remote_id],
                "summary": "Manual title",
                "start": {"dateTime": (NOW + timedelta(hours=2)).isoformat()},
                "end": {"dateTime": (NOW + timedelta(hours=3)).isoformat()},
            }
        )
        return original(calendar_id, remote_id, payload, etag=etag)

    provider.update_event = racing_update
    assert publish(calendar_scenario).state == "CONFLICT"
    assert next(iter(provider.events.values()))["summary"] == "Manual title"
    with Session(engine) as db:
        mapping = db.scalar(select(BlockEventMapping))
        assert mapping.commitment["start"] == (NOW + timedelta(hours=2)).isoformat()


def test_publication_discovered_move_revisions_inputs_and_enqueues_replan(calendar_scenario):
    from planner.db.models import PendingReplan

    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    sync(calendar_scenario)
    remote = next(iter(provider.events.values()))
    provider.put_external(
        {
            **remote,
            "start": {"dateTime": (NOW + timedelta(hours=2)).isoformat()},
            "end": {"dateTime": (NOW + timedelta(hours=3)).isoformat()},
        }
    )
    activate(calendar_scenario)
    assert publish(calendar_scenario).state == "CONFLICT"
    with Session(engine) as db:
        assert db.get(PlanningState, owner).revision == 1
        assert db.get(PlanningState, owner).calendar_revision == 1
        assert db.get(PendingReplan, owner).desired_revision == 1
    sync(calendar_scenario)
    with Session(engine) as db:
        assert db.get(PlanningState, owner).revision == 1


def test_timeout_after_remote_update_reconciles_own_changed_etag(calendar_scenario):
    from planner.db.models import Task

    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    with Session(engine) as db, db.begin():
        db.scalar(select(Task)).title = "New reviewed title"
    activate(calendar_scenario)
    provider.timeout_after_write = True
    assert publish(calendar_scenario).state == "PARTIAL"
    assert publish(calendar_scenario).state == "PUBLISHED"
    assert len(provider.writes) == 2
    assert next(iter(provider.events.values()))["summary"] == "New reviewed title"


def test_mapping_operation_link_rejects_cross_owner_sql(calendar_scenario):
    import pytest
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    from planner.calendar.fake import FakeCalendarProvider
    from tests.integration.test_jobs import seed_owner

    engine, owner, _ = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    other = seed_owner(engine, 2)
    with Session(engine) as db, db.begin():
        db.add(CalendarConnection(owner_id=other, provider="MOCK", calendar_id="other"))
    other_scenario = engine, other, FakeCalendarProvider()
    activate(other_scenario)
    publish(other_scenario)
    with Session(engine) as db:
        other_operation = db.scalar(
            select(CalendarWriteOperation.id).where(CalendarWriteOperation.owner_id == other)
        )
    with pytest.raises(IntegrityError), Session(engine) as db, db.begin():
        db.execute(
            update(BlockEventMapping)
            .where(BlockEventMapping.owner_id == owner)
            .values(operation_id=other_operation)
        )


def test_off_grid_manual_move_is_visible_invalid_input_without_worker_crash(calendar_scenario):
    from planner.jobs.dispatcher import capture_snapshot
    from planner.solver.cp_sat import solve_cp_sat

    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    remote = next(iter(provider.events.values()))
    moved_start, moved_end = (
        NOW + timedelta(hours=2, minutes=7),
        NOW + timedelta(hours=3, minutes=7),
    )
    provider.put_external(
        {
            **remote,
            "start": {"dateTime": moved_start.isoformat()},
            "end": {"dateTime": moved_end.isoformat()},
        }
    )
    sync(calendar_scenario)
    with Session(engine) as db:
        captured = capture_snapshot(db, owner, NOW)
        assert db.scalar(select(CalendarConflict)).reason == "MANUAL_EDIT"
    assert captured.protected_blocks[0].original_start == moved_start
    assert captured.protected_blocks[0].start == NOW + timedelta(hours=2)
    assert captured.protected_blocks[0].end == NOW + timedelta(hours=3, minutes=15)
    assert captured.busy_slot_ranges == ((44, 49),)
    candidate = solve_cp_sat(captured)
    assert candidate.status == "MODEL_INVALID"
    assert "CALENDAR_OFF_GRID" in {v.code for v in candidate.constraint_report}
    assert next(iter(provider.events.values()))["start"]["dateTime"] == moved_start.isoformat()
    enqueue(engine, owner, now=NOW, explicit=True)
    claim = claim_next(engine, now=NOW)
    assert claim is not None
    completed = finalize(engine, claim, solve_cp_sat(claim.snapshot), now=NOW)
    assert completed.state == "FAILED"


def test_explicit_restore_is_revisioned_and_reconciles_to_active_plan(calendar_scenario):
    from types import SimpleNamespace
    from uuid import uuid4

    from starlette.requests import Request

    from planner.api.auth import Principal
    from planner.api.calendar import ResolveCalendarConflict, resolve_calendar_conflict

    engine, owner, provider = calendar_scenario
    activate(calendar_scenario)
    publish(calendar_scenario)
    remote = next(iter(provider.events.values()))
    provider.put_external(
        {
            **remote,
            "start": {"dateTime": (NOW + timedelta(hours=2)).isoformat()},
            "end": {"dateTime": (NOW + timedelta(hours=3)).isoformat()},
        }
    )
    sync(calendar_scenario)
    with Session(engine) as db:
        conflict_id = db.scalar(select(CalendarConflict.id))
        revision = db.get(PlanningState, owner).revision
    request = Request(
        {
            "type": "http",
            "headers": [(b"idempotency-key", str(uuid4()).encode())],
            "app": SimpleNamespace(state=SimpleNamespace(engine=engine, clock=lambda: NOW)),
        }
    )
    response = resolve_calendar_conflict(
        conflict_id,
        ResolveCalendarConflict(expected_revision=revision, action="RESTORE"),
        request,
        Principal(owner, "csrf", "hash"),
    )
    assert response["revision"] == revision + 1
    assert publish(calendar_scenario).state == "PUBLISHED"
    assert next(iter(provider.events.values()))["start"]["dateTime"] == NOW.isoformat()
    with Session(engine) as db:
        assert db.scalar(select(BlockEventMapping)).commitment is None
        assert db.scalar(select(CalendarConflict)).state == "RESOLVED"
