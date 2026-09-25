"""All pages become visible together; PostgreSQL is the authority."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from planner.calendar.fake import FakeCalendarProvider
from planner.db.calendar_models import CalendarConnection, EventMirror
from planner.db.models import PlanningState
from tests.integration.test_jobs import NOW, seed_owner


@pytest.fixture
def calendar_scenario(migrated_database_url):
    engine = create_engine(migrated_database_url)
    owner = seed_owner(engine)
    with Session(engine) as db, db.begin():
        db.add(CalendarConnection(owner_id=owner, provider="MOCK", calendar_id="synthetic"))
    yield engine, owner, FakeCalendarProvider(page_size=1)
    engine.dispose()


def event(identity, **changes):
    return {
        "id": identity,
        "start": {"dateTime": NOW.isoformat()},
        "end": {"dateTime": (NOW + timedelta(hours=1)).isoformat()},
        **changes,
    }


def sync(scenario):
    from planner.calendar.sync import synchronize

    engine, owner, provider = scenario
    return synchronize(
        engine, owner, provider, now=NOW, window_start=NOW, window_end=NOW + timedelta(days=14)
    )


def test_incomplete_sync_does_not_advance_cursor_or_expose_partial_mirror(calendar_scenario):
    engine, owner, provider = calendar_scenario
    provider.put_external(event("first"))
    assert sync(calendar_scenario).state == "SYNCED"
    with Session(engine) as db:
        old_cursor = db.get(CalendarConnection, owner).sync_token
    provider.put_external(event("second"))
    provider.put_external(event("third"))
    provider.fail_on_page = 2
    assert sync(calendar_scenario).state == "RETRYABLE"
    with Session(engine) as db:
        assert db.get(CalendarConnection, owner).sync_token == old_cursor
        assert len(list(db.scalars(select(EventMirror)))) == 1
        assert db.get(PlanningState, owner).revision == 1
    provider.fail_on_page = None
    assert sync(calendar_scenario).state == "SYNCED"
    with Session(engine) as db:
        assert len(list(db.scalars(select(EventMirror)))) == 3
        # All three events occupy the same interval: effective busy has not changed.
        assert db.get(PlanningState, owner).revision == 1


def test_noop_transparent_and_cancelled_are_not_busy(calendar_scenario):
    engine, owner, provider = calendar_scenario
    provider.put_external(event("clear", transparency="transparent"))
    provider.put_external(event("deleted", status="cancelled"))
    assert sync(calendar_scenario).state == "SYNCED"
    assert sync(calendar_scenario).state == "SYNCED"
    with Session(engine) as db:
        assert db.get(PlanningState, owner).revision == 0
    provider.put_external(event("busy", recurringEventId="recurring"))
    sync(calendar_scenario)
    provider.put_external({"id": "busy", "status": "cancelled"})
    sync(calendar_scenario)
    with Session(engine) as db:
        assert db.get(PlanningState, owner).revision == 2


def test_invalid_cursor_rebuilds_without_touching_tasks(calendar_scenario):
    from planner.db.models import Task

    engine, owner, provider = calendar_scenario
    provider.put_external(event("first"))
    sync(calendar_scenario)
    provider.invalid_token_once = True
    provider.put_external(event("second"))
    assert sync(calendar_scenario).state == "SYNCED"
    with Session(engine) as db:
        assert len(list(db.scalars(select(EventMirror)))) == 2
        assert len(list(db.scalars(select(Task).where(Task.owner_id == owner)))) == 1


def test_refresh_authentication_failure_needs_reauth(calendar_scenario):
    engine, owner, provider = calendar_scenario
    provider.authentication_required = True
    assert sync(calendar_scenario).state == "AUTHENTICATION_REQUIRED"
    with Session(engine) as db:
        assert db.get(CalendarConnection, owner).state == "NEEDS_REAUTH"


def test_stale_sync_auth_failure_cannot_overwrite_disconnect(calendar_scenario):
    from planner.calendar.provider import ProviderError

    engine, owner, provider = calendar_scenario

    def old_call(*args, **kwargs):
        with Session(engine) as db, db.begin():
            connection = db.get(CalendarConnection, owner)
            connection.state = "DISCONNECTING"
            connection.generation += 1
        raise ProviderError("AUTHENTICATION_REQUIRED")

    provider.list_events = old_call
    assert sync(calendar_scenario).state == "SUPERSEDED"
    with Session(engine) as db:
        assert db.get(CalendarConnection, owner).state == "DISCONNECTING"
