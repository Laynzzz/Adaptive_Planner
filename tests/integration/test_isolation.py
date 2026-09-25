"""Authorization must run before serving user data."""

from fastapi.testclient import TestClient

from planner.app import create_app
from planner.settings import Settings


def test_anonymous_requests_cannot_read_personal_data(migrated_database_url):
    with TestClient(create_app(Settings(database_url=migrated_database_url))) as api:
        for path in ("/api/v1/me", "/api/v1/tasks", "/api/v1/availability"):
            assert api.get(path).status_code == 401


def test_real_provider_creates_two_distinct_sessions(api_a, api_b):
    first, second = api_a.get("/api/v1/me"), api_b.get("/api/v1/me")
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["csrf_token"] != second.json()["csrf_token"]
    assert first.json()["revision"] == second.json()["revision"] == 0


def test_callback_rejects_missing_login_state(app):
    with TestClient(app) as api:
        response = api.get("/api/v1/auth/callback?code=forged&state=forged")
    assert response.status_code == 400


def test_other_owner_cannot_read_or_mutate_task(api_a, api_b):
    from uuid import uuid4

    from tests.integration.test_commands import command, post

    created = post(api_a, command()).json()
    path = f"/api/v1/tasks/{created['id']}"
    assert api_b.get(path).status_code == 404
    changed = api_b.patch(
        path,
        json={"expected_revision": 0, "title": "Intrusion"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert changed.status_code == 404
    assert api_b.get("/api/v1/tasks").json()["items"] == []
    assert api_a.get(path).json()["title"] == "Synthetic draft"


def test_cross_owner_dependency_is_rejected_by_api_and_database(
    api_a, api_b, migrated_database_url
):
    from uuid import UUID, uuid4

    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from planner.db.models import DependencyEdge
    from tests.integration.test_commands import command, post

    first = post(api_a, command()).json()
    second = post(api_b, command()).json()
    result = api_a.post(
        f"/api/v1/tasks/{first['id']}/dependencies",
        json={"predecessor_id": second["id"], "expected_revision": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 404
    engine = create_engine(migrated_database_url)
    with Session(engine) as db, pytest.raises(IntegrityError), db.begin():
        db.add(
            DependencyEdge(
                owner_id=UUID(first["owner_id"]),
                predecessor_id=UUID(second["id"]),
                successor_id=UUID(first["id"]),
            )
        )
        db.flush()
    engine.dispose()


def test_logout_revokes_server_session(api_a):
    token = api_a.cookies.get("planner_session")
    assert api_a.post("/api/v1/auth/logout").status_code == 204
    api_a.cookies.set("planner_session", token, domain="127.0.0.1", path="/")
    assert api_a.get("/api/v1/me").status_code == 401


def test_expired_session_cannot_replay_receipt(api_a, migrated_database_url):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import create_engine, update

    from planner.db.models import BrowserSession
    from tests.integration.test_commands import command, post

    assert post(api_a, command(), "expiry-test").status_code == 201
    engine = create_engine(migrated_database_url)
    with engine.begin() as db:
        db.execute(
            update(BrowserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    engine.dispose()
    assert post(api_a, command(), "expiry-test").status_code == 401


def test_untrusted_origin_cannot_mutate(api_a):
    from uuid import uuid4

    from tests.integration.test_commands import command

    response = api_a.post(
        "/api/v1/tasks",
        json=command(),
        headers={"Origin": "https://untrusted.example", "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 403
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_private_api_responses_disable_shared_caching(api_a):
    assert api_a.get("/api/v1/me").headers.get("Cache-Control") == "no-store"


def test_login_cookie_is_opaque_and_http_only(app):
    with TestClient(app, base_url="http://127.0.0.1:8000") as api:
        response = api.get("/api/v1/auth/login", follow_redirects=False)
        header = response.headers["set-cookie"]
        assert "HttpOnly" in header
        assert "SameSite=lax" in header
        assert "nonce" not in header
        assert "code_verifier" not in header
