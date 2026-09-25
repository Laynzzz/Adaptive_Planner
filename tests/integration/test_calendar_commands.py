# ruff: noqa: F811 -- imported pytest fixtures are deliberately injected by name.
from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from planner.db.calendar_models import CalendarConnection
from tests.integration.test_calendar_sync import calendar_scenario  # noqa: F401
from tests.integration.test_jobs import NOW


def test_calendar_queue_survives_expired_worker_lease(calendar_scenario):
    from planner.calendar.worker import run_calendar_once

    engine, owner, provider = calendar_scenario
    with Session(engine) as db, db.begin():
        connection = db.get(CalendarConnection, owner)
        connection.sync_request = uuid4()
        connection.io_lease_token, connection.io_lease_until = uuid4(), NOW - timedelta(seconds=1)
    assert run_calendar_once(engine, lambda _: provider, clock=lambda: NOW)
    with Session(engine) as db:
        connection = db.get(CalendarConnection, owner)
        assert connection.sync_request is None
        assert connection.sync_token == "0"


def test_disconnect_stops_writes_and_clears_credentials(calendar_scenario):
    from planner.calendar.worker import run_calendar_once

    engine, owner, provider = calendar_scenario
    with Session(engine) as db, db.begin():
        connection = db.get(CalendarConnection, owner)
        connection.state, connection.keep_remote_events = "DISCONNECTING", True
        connection.encrypted_refresh_token = "synthetic-ciphertext"
    assert run_calendar_once(engine, lambda _: provider, clock=lambda: NOW)
    assert provider.writes == []
    with Session(engine) as db:
        connection = db.get(CalendarConnection, owner)
        assert connection.state == "DISCONNECTED"
        assert connection.encrypted_refresh_token is None


def test_disconnect_attempts_revocation_but_does_not_retain_failed_credentials(calendar_scenario):
    from planner.calendar.provider import ProviderError
    from planner.calendar.worker import run_calendar_once

    engine, owner, provider = calendar_scenario
    observed = []

    def revoke():
        observed.append("revoked")
        raise ProviderError("RETRYABLE")

    provider.revoke_credentials = revoke
    with Session(engine) as db, db.begin():
        connection = db.get(CalendarConnection, owner)
        connection.state, connection.keep_remote_events = "DISCONNECTING", True
        connection.encrypted_refresh_token = "synthetic-ciphertext"
    run_calendar_once(engine, lambda _: provider, clock=lambda: NOW)
    assert observed == ["revoked"]
    with Session(engine) as db:
        connection = db.get(CalendarConnection, owner)
        assert connection.state == "DISCONNECTED"
        assert connection.encrypted_refresh_token is None
        assert connection.last_error == "REVOCATION_UNCONFIRMED"


def test_calendar_endpoints_label_mock_enforce_revision_and_owner(api_a, api_b, app):
    from planner.api.calendar import router

    if not any(r.path == "/api/v1/calendar/status" for r in app.routes):
        app.include_router(router)
    assert api_a.get("/api/v1/calendar/status").json()["live_configured"] is False
    revision = api_a.get("/api/v1/me").json()["revision"]
    payload = {
        "provider": "MOCK",
        "calendar_id": "synthetic-demo",
        "dedicated_synthetic_confirmed": True,
        "expected_revision": revision,
    }
    response = api_a.post("/api/v1/calendar/connect", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "CONNECTED"
    assert api_a.get("/api/v1/calendar/status").json()["provider"] == "MOCK"
    assert api_b.get("/api/v1/calendar/status").json()["state"] == "DISCONNECTED"
    assert (
        api_a.post("/api/v1/calendar/sync", json={"expected_revision": revision}).status_code == 409
    )
    queued = api_a.post("/api/v1/calendar/sync", json={"expected_revision": revision + 1})
    assert queued.status_code == 200
    assert queued.json()["revision"] == revision + 1


def test_google_is_disabled_and_calendar_mutations_require_csrf(api_a, app):
    from planner.api.calendar import router

    if not any(r.path == "/api/v1/calendar/status" for r in app.routes):
        app.include_router(router)
    payload = {
        "provider": "GOOGLE",
        "calendar_id": "synthetic@group.calendar.google.com",
        "dedicated_synthetic_confirmed": True,
        "expected_revision": 0,
    }
    response = api_a.post("/api/v1/calendar/connect", json=payload)
    assert response.status_code == 503, response.text
    assert api_a.get("/api/v1/me").json()["revision"] == 0
    response = api_a.post(
        "/api/v1/calendar/connect", json=payload, headers={"X-CSRF-Token": "wrong"}
    )
    assert response.status_code == 403


def test_old_worker_auth_failure_cannot_replace_new_disconnect(calendar_scenario):
    from planner.calendar.provider import ProviderError
    from planner.calendar.worker import run_calendar_once

    engine, owner, provider = calendar_scenario
    with Session(engine) as db, db.begin():
        db.get(CalendarConnection, owner).sync_request = uuid4()

    def factory(_):
        with Session(engine) as db, db.begin():
            connection = db.get(CalendarConnection, owner)
            connection.state = "DISCONNECTING"
            connection.sync_request = None
            connection.generation += 1
        raise ProviderError("AUTHENTICATION_REQUIRED")

    assert run_calendar_once(engine, factory, clock=lambda: NOW)
    with Session(engine) as db:
        assert db.get(CalendarConnection, owner).state == "DISCONNECTING"
