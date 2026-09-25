from datetime import UTC, datetime

from sqlalchemy.orm import Session

from planner.jobs.dispatcher import capture_snapshot
from tests.integration.test_adaptation import create_task


def add_rule(api, kind, weekday, revision):
    return api.post(
        "/api/v1/weekday-rules",
        json={"kind": kind, "weekday": weekday, "expected_revision": revision},
    )


def test_rule_kind_semantics_and_owner_scoping(api_a, api_b, app):
    task = create_task(api_a, app)
    result = add_rule(api_a, "HARD_UNAVAILABLE", 4, task["revision"])
    assert result.status_code == 201, result.text
    rule = result.json()
    view = api_a.get("/api/v1/weekday-rules").json()
    assert view["items"] == [{"id": rule["id"], "kind": "HARD_UNAVAILABLE", "weekday": 4}]
    assert api_b.get("/api/v1/weekday-rules").json()["items"] == []
    denied = api_b.raw.request(
        "DELETE",
        "/api/v1/weekday-rules/" + rule["id"],
        headers={"Idempotency-Key": "delete-other"},
        json={"expected_revision": 0},
    )
    assert denied.status_code == 404
    owner = task["owner_id"]
    from uuid import UUID

    with Session(app.state.engine) as db:
        snapshot = capture_snapshot(db, UUID(owner), app.state.clock())
        assert snapshot.busy_slot_ranges[0] == (36, 96)
        assert snapshot.tasks[0].deadline_at.hour == 17
    deleted = api_a.raw.request(
        "DELETE",
        "/api/v1/weekday-rules/" + rule["id"],
        headers={"Idempotency-Key": "delete-own"},
        json={"expected_revision": rule["revision"]},
    )
    assert deleted.status_code == 200


def test_no_deadline_rule_rejects_existing_and_future_conflicts_atomically(api_a, app):
    task = create_task(api_a, app)
    denied = add_rule(api_a, "HARD_NO_DEADLINE", 4, task["revision"])
    assert denied.status_code == 409 and denied.json()["code"] == "DEADLINE_WEEKDAY_FORBIDDEN"
    assert api_a.get("/api/v1/weekday-rules").json()["items"] == []
    assert api_a.get("/api/v1/me").json()["revision"] == task["revision"]
    accepted = add_rule(api_a, "HARD_NO_DEADLINE", 5, task["revision"]).json()
    edited = api_a.patch(
        "/api/v1/tasks/" + task["id"],
        json={
            "deadline": {"kind": "DATE", "value": "2026-09-26"},
            "expected_revision": accepted["revision"],
        },
    )
    assert edited.status_code == 409 and edited.json()["code"] == "DEADLINE_WEEKDAY_FORBIDDEN"
    preview = api_a.post(
        "/api/v1/what-ifs",
        json={
            "expected_revision": accepted["revision"],
            "task_changes": [
                {"task_id": task["id"], "deadline": {"kind": "DATE", "value": "2026-09-26"}}
            ],
        },
    )
    assert preview.status_code == 409 and preview.json()["code"] == "DEADLINE_WEEKDAY_FORBIDDEN"


def test_soft_avoid_does_not_remove_availability_or_create_busy(api_a, app):
    task = create_task(api_a, app)
    rule = add_rule(api_a, "SOFT_AVOID", 4, task["revision"])
    assert rule.status_code == 201, rule.text
    from uuid import UUID

    with Session(app.state.engine) as db:
        snapshot = capture_snapshot(db, UUID(task["owner_id"]), app.state.clock())
        assert snapshot.busy_slot_ranges == ()
        assert snapshot.preferred_windows[0][0] == 96


def test_rule_expansion_uses_actual_dst_local_day_length():
    from planner.domain.weekday_rules import expand_weekday_rules

    raw = {"timezone": "America/New_York", "tasks": [], "availability": [], "fixed_events": []}
    result = expand_weekday_rules(
        raw, [("HARD_UNAVAILABLE", 6)], datetime(2026, 11, 1, 4, tzinfo=UTC)
    )
    interval = result["fixed_events"][0]
    assert interval["start"] == datetime(2026, 11, 1, 4, tzinfo=UTC)
    assert interval["end"] == datetime(2026, 11, 2, 5, tzinfo=UTC)


def test_task_creation_checks_timestamp_in_owner_timezone(api_a, app):
    from uuid import UUID

    from planner.db.models import Identity

    task = create_task(api_a, app)
    with Session(app.state.engine) as db, db.begin():
        db.get(Identity, UUID(task["owner_id"])).timezone = "America/New_York"
    rule = add_rule(api_a, "HARD_NO_DEADLINE", 5, task["revision"]).json()
    rejected = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "Forbidden Saturday",
            "remaining_minutes": 30,
            "deadline": {"kind": "TIMESTAMP", "value": "2026-09-27T01:00:00Z"},
            "expected_revision": rule["revision"],
        },
    )
    assert rejected.status_code == 409 and rejected.json()["code"] == "DEADLINE_WEEKDAY_FORBIDDEN"
    accepted = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "Allowed local Friday",
            "remaining_minutes": 30,
            "deadline": {"kind": "TIMESTAMP", "value": "2026-09-26T01:00:00Z"},
            "expected_revision": rule["revision"],
        },
    )
    assert accepted.status_code == 201, accepted.text


def test_new_unavailability_rejects_locked_work_without_committing_rule(api_a, app):
    from tests.integration.test_adaptation import create_selected_plan

    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    block = api_a.get("/api/v1/active-plan").json()["candidate"]["blocks"][0]
    locked = api_a.post(
        "/api/v1/blocks/" + block["id"] + "/lock",
        json={"locked": True, "expected_revision": revision},
    )
    response = add_rule(api_a, "HARD_UNAVAILABLE", 4, locked.json()["revision"])
    assert response.status_code == 409 and response.json()["code"] == "PROTECTED_BUSY_CONFLICT"
    assert api_a.get("/api/v1/weekday-rules").json()["items"] == []
    assert api_a.get("/api/v1/me").json()["revision"] == locked.json()["revision"]
