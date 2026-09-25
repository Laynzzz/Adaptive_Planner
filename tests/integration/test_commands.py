"""Atomic revision and idempotency contracts on real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from planner.db.models import AuditEvent, CommandReceipt, PendingReplan, Task


def command(revision=0, **changes):
    payload = {
        "title": "Synthetic draft",
        "remaining_minutes": 60,
        "expected_revision": revision,
        "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T17:00:00Z", "timezone": "UTC"},
    }
    payload.update(changes)
    return payload


def post(api, payload, key=None):
    return api.post("/api/v1/tasks", json=payload, headers={"Idempotency-Key": key or str(uuid4())})


def test_input_commit_increments_revision_and_persists_receipt_audit_and_demand(
    api_a, migrated_database_url
):
    result = post(api_a, command())
    assert result.status_code == 201, result.text
    assert result.json()["revision"] == 1
    assert api_a.get("/api/v1/me").json()["revision"] == 1
    engine = create_engine(migrated_database_url)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Task)) == 1
        assert db.scalar(select(func.count()).select_from(CommandReceipt)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1
        assert db.scalar(select(PendingReplan.desired_revision)) == 1
    engine.dispose()


def test_retry_returns_original_response_without_increment(api_a):
    key = str(uuid4())
    first = post(api_a, command(), key)
    assert first.status_code == 201, first.text
    second = post(api_a, command(), key)
    assert second.status_code == 201
    assert second.json() == first.json()
    assert api_a.get("/api/v1/me").json()["revision"] == 1
    changed = post(api_a, command(title="Changed"), key)
    assert changed.status_code == 409
    assert changed.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_competing_same_revision_commands_commit_exactly_once(api_a):
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: post(api_a, command()), range(2)))
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert api_a.get("/api/v1/me").json()["revision"] == 1
    assert len(api_a.get("/api/v1/tasks").json()["items"]) == 1


def test_missing_csrf_does_not_mutate(api_a):
    response = api_a.post(
        "/api/v1/tasks",
        json=command(),
        headers={"X-CSRF-Token": "", "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 403
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_missing_idempotency_key_does_not_mutate(api_a):
    response = api_a.raw.post("/api/v1/tasks", json=command())
    assert response.status_code == 400
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_dependency_cycle_rolls_back_revision(api_a):
    first = post(api_a, command()).json()
    second = post(api_a, command(1, title="Second")).json()
    good = api_a.post(
        f"/api/v1/tasks/{second['id']}/dependencies",
        json={"predecessor_id": first["id"], "expected_revision": 2},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert good.status_code == 200, good.text
    bad = api_a.post(
        f"/api/v1/tasks/{first['id']}/dependencies",
        json={"predecessor_id": second["id"], "expected_revision": 3},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "DEPENDENCY_CYCLE"
    assert api_a.get("/api/v1/me").json()["revision"] == 3


def test_availability_and_fixed_events_validate_and_are_owner_scoped(api_a, api_b):
    window = {"start": "2026-09-25T09:00:00Z", "end": "2026-09-25T17:00:00Z"}
    result = api_a.put(
        "/api/v1/availability",
        json={"windows": [window], "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 200
    assert result.json()["revision"] == 1
    assert api_b.get("/api/v1/availability").json()["windows"] == []
    invalid = api_a.post(
        "/api/v1/fixed-events",
        json={
            "title": "Invalid",
            "start": window["end"],
            "end": window["start"],
            "expected_revision": 1,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert invalid.status_code == 422
    valid = api_a.post(
        "/api/v1/fixed-events",
        json={"title": "Meeting", **window, "expected_revision": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert valid.status_code == 201
    assert api_b.get("/api/v1/fixed-events").json()["items"] == []
    assert api_a.get("/api/v1/me").json()["revision"] == 2


def test_audit_rows_cannot_be_rewritten(api_a, migrated_database_url):
    import pytest
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError

    assert post(api_a, command()).status_code == 201
    engine = create_engine(migrated_database_url)
    with engine.connect() as db, pytest.raises(DBAPIError):
        db.execute(update(AuditEvent).values(revision=999))
        db.commit()
    engine.dispose()


def test_expired_receipt_cannot_override_current_revision(api_a, migrated_database_url):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    assert post(api_a, command(), "old-key").status_code == 201
    engine = create_engine(migrated_database_url)
    with engine.begin() as db:
        db.execute(
            update(CommandReceipt).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    engine.dispose()
    response = post(api_a, command(), "old-key")
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_REVISION"
    assert len(api_a.get("/api/v1/tasks").json()["items"]) == 1


def test_coalescing_preserves_oldest_enqueue(api_a, migrated_database_url):
    engine = create_engine(migrated_database_url)
    assert post(api_a, command()).status_code == 201
    with Session(engine) as db:
        original = db.scalar(select(PendingReplan.enqueued_at))
    assert post(api_a, command(1, title="Second")).status_code == 201
    with Session(engine) as db:
        pending = db.scalar(select(PendingReplan))
        assert pending.enqueued_at == original
        assert pending.desired_revision == 2
    engine.dispose()


def test_task_patch_cancel_and_cursor_binding(api_a):
    first = post(api_a, command()).json()
    post(api_a, command(1, title="Second"))
    page = api_a.get("/api/v1/tasks?limit=1").json()
    assert page["next_cursor"]
    assert (
        api_a.get(
            "/api/v1/tasks", params={"cursor": page["next_cursor"], "state": "DONE"}
        ).status_code
        == 400
    )
    post(api_a, command(2, title="Inserted after scan"))
    next_page = api_a.get("/api/v1/tasks", params={"cursor": page["next_cursor"]}).json()
    assert len(next_page["items"]) == 1
    assert next_page["items"][0]["title"] == "Second"
    changed = api_a.patch(
        f"/api/v1/tasks/{first['id']}",
        json={"expected_revision": 3, "title": "Edited"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert changed.status_code == 200
    assert changed.json()["title"] == "Edited"
    cancelled = api_a.post(
        f"/api/v1/tasks/{first['id']}/cancel",
        json={"expected_revision": 4},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "CANCELLED"


def test_seed_demo_uses_authenticated_identities_and_is_idempotent(
    api_a, api_b, migrated_database_url
):
    import os
    import subprocess
    import sys

    env = {**os.environ, "PLANNER_DATABASE_URL": migrated_database_url}
    first = subprocess.run(
        [sys.executable, "-m", "planner.cli", "seed-demo"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    assert len(api_a.get("/api/v1/tasks").json()["items"]) == 2
    assert len(api_b.get("/api/v1/tasks").json()["items"]) == 2
    second = subprocess.run(
        [sys.executable, "-m", "planner.cli", "seed-demo"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert second.returncode == 0
    assert len(api_a.get("/api/v1/tasks").json()["items"]) == 2
    assert api_a.get("/api/v1/me").json()["revision"] == 1


def test_invalid_timezone_is_a_client_error_without_revision_change(api_a):
    result = post(
        api_a, command(deadline={"kind": "DATE", "value": "2026-09-27", "timezone": "Mars/City"})
    )
    assert result.status_code == 422
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_effort_outside_persistence_range_is_a_client_error(api_a):
    response = post(api_a, command(remaining_minutes=3_000_000_000))
    assert response.status_code == 422
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_malformed_cursor_shape_is_a_client_error(api_a):
    import base64
    import json

    owner = api_a.get("/api/v1/me").json()["id"]
    cursor = base64.urlsafe_b64encode(
        json.dumps({"owner": owner, "state": None, "upper": [], "after": []}).encode()
    ).decode()
    response = api_a.get("/api/v1/tasks", params={"cursor": cursor})
    assert response.status_code == 400
    assert response.json()["code"] == "CURSOR_INVALID"


def test_availability_payload_and_revision_share_one_database_snapshot(
    api_a, app, migrated_database_url
):
    from uuid import UUID

    from sqlalchemy import event, update

    from planner.db.models import Availability, PlanningState

    original = [{"start": "2026-09-25T09:00:00Z", "end": "2026-09-25T10:00:00Z"}]
    newer = [{"start": "2026-09-25T11:00:00Z", "end": "2026-09-25T12:00:00Z"}]
    assert (
        api_a.put(
            "/api/v1/availability", json={"windows": original, "expected_revision": 0}
        ).status_code
        == 200
    )
    owner = UUID(api_a.get("/api/v1/me").json()["id"])
    writer = create_engine(migrated_database_url)
    fired = False

    def commit_between_reads(connection, cursor, statement, parameters, context, executemany):
        nonlocal fired
        if (
            fired
            or not statement.lstrip().startswith("SELECT")
            or "availability_rules" not in statement
        ):
            return
        fired = True
        with writer.begin() as db:
            db.execute(
                update(Availability).where(Availability.owner_id == owner).values(windows=newer)
            )
            db.execute(
                update(PlanningState).where(PlanningState.owner_id == owner).values(revision=2)
            )

    event.listen(app.state.engine, "after_cursor_execute", commit_between_reads)
    try:
        result = api_a.get("/api/v1/availability").json()
    finally:
        event.remove(app.state.engine, "after_cursor_execute", commit_between_reads)
        writer.dispose()
    assert fired
    assert result["windows"] == original
    assert result["revision"] == 1
    stale = api_a.put(
        "/api/v1/availability",
        json={"windows": result["windows"], "expected_revision": result["revision"]},
    )
    assert stale.status_code == 409
    assert api_a.get("/api/v1/availability").json()["windows"] == newer
