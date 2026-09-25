"""Fixed-event deletion is an owner-scoped, atomic planning command."""

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from planner.db.models import PendingReplan


def test_delete_fixed_event_checks_owner_revision_and_replays_without_new_demand(api_a, api_b, app):
    event = api_a.post(
        "/api/v1/fixed-events",
        json={
            "title": "Synthetic meeting",
            "start": "2026-09-26T10:00:00Z",
            "end": "2026-09-26T11:00:00Z",
            "expected_revision": 0,
        },
    ).json()
    path = "/api/v1/fixed-events/" + event["id"]

    def remove(api, revision, key=None):
        return api.request(
            "DELETE",
            path,
            json={"expected_revision": revision},
            headers={"Idempotency-Key": key or str(uuid4())},
        )

    foreign = remove(api_b, 0)
    assert foreign.status_code == 404
    stale = remove(api_a, 0)
    assert stale.status_code == 409 and stale.json()["code"] == "STALE_REVISION"
    assert len(api_a.get("/api/v1/fixed-events").json()["items"]) == 1
    key = str(uuid4())
    deleted = remove(api_a, 1, key)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"revision": 2}
    assert api_a.get("/api/v1/fixed-events").json()["items"] == []
    replay = remove(api_a, 1, key)
    assert replay.json() == deleted.json() and replay.status_code == 200
    assert api_a.get("/api/v1/me").json()["revision"] == 2
    assert api_b.get("/api/v1/me").json()["revision"] == 0
    owner = UUID(api_a.get("/api/v1/me").json()["id"])
    with Session(app.state.engine) as db:
        assert db.get(PendingReplan, owner).desired_revision == 2
    assert remove(api_a, 2).status_code == 404
    assert api_a.get("/api/v1/me").json()["revision"] == 2


def test_task_patch_cannot_reduce_estimate_below_protected_work(api_a, app):
    from datetime import UTC, datetime, timedelta

    from planner.db.adaptation_models import ProtectedWork

    task = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "Protected synthetic task",
            "remaining_minutes": 60,
            "expected_revision": 0,
        },
    ).json()
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    with Session(app.state.engine) as db, db.begin():
        db.add(
            ProtectedWork(
                owner_id=UUID(task["owner_id"]),
                id=uuid4(),
                task_id=UUID(task["id"]),
                start=now,
                end=now + timedelta(minutes=60),
                source="MANUAL",
                locked=True,
            )
        )
    changed = api_a.patch(
        "/api/v1/tasks/" + task["id"],
        json={
            "title": "Must roll back",
            "remaining_minutes": 15,
            "expected_revision": 1,
        },
    )
    assert changed.status_code == 409
    assert changed.json()["code"] == "LOCK_EXCEEDS_REMAINING"
    unchanged = api_a.get("/api/v1/tasks/" + task["id"]).json()
    assert unchanged["remaining_minutes"] == 60 and unchanged["title"] == "Protected synthetic task"
    assert unchanged["revision"] == 1
    with Session(app.state.engine) as db:
        assert db.get(PendingReplan, UUID(task["owner_id"])).desired_revision == 1
    increased = api_a.patch(
        "/api/v1/tasks/" + task["id"],
        json={
            "remaining_minutes": 90,
            "expected_revision": 1,
        },
    )
    assert increased.status_code == 200 and increased.json()["revision"] == 2
    assert increased.json()["remaining_minutes"] == 90


def test_cancel_releases_protected_inputs_but_preserves_proposal_and_replays(api_a, app):
    from tests.integration.test_adaptation import create_selected_plan

    task, revision, proposal_id, _ = create_selected_plan(api_a, app)
    candidate = api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"]
    block = candidate["blocks"][0]
    locked = api_a.post(
        f"/api/v1/blocks/{block['id']}/lock", json={"locked": True, "expected_revision": revision}
    )
    assert locked.status_code == 200
    assert len(api_a.get("/api/v1/protected-work").json()["items"]) == 1
    revision = locked.json()["revision"]
    key = str(uuid4())
    args = {"json": {"expected_revision": revision}, "headers": {"Idempotency-Key": key}}
    cancelled = api_a.post(f"/api/v1/tasks/{task['id']}/cancel", **args)
    assert cancelled.status_code == 200
    assert api_a.get("/api/v1/protected-work").json()["items"] == []
    assert api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"] == candidate
    replay = api_a.post(f"/api/v1/tasks/{task['id']}/cancel", **args)
    assert replay.json() == cancelled.json()
    assert api_a.get("/api/v1/me").json()["revision"] == revision + 1
