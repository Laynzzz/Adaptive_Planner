"""Explicit progress and what-if changes never silently alter selected work."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import finalize
from planner.solver.greedy import greedy_schedule
from tests.integration.test_jobs import NOW


def create_task(api, app):
    app.state.clock = lambda: NOW
    revision = api.get("/api/v1/me").json()["revision"]
    result = api.post(
        "/api/v1/tasks",
        json={
            "title": "Draft",
            "remaining_minutes": 60,
            "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T17:00Z"},
            "expected_revision": revision,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def create_selected_plan(api, app):
    task = create_task(api, app)
    availability = api.put(
        "/api/v1/availability",
        json={
            "windows": [{"start": "2026-09-25T09:00Z", "end": "2026-09-25T17:00Z"}],
            "expected_revision": task["revision"],
        },
    )
    revision = availability.json()["revision"]
    api.post("/api/v1/replans", json={"expected_revision": revision})
    claim = claim_next(app.state.engine, now=NOW)
    finish = finalize(app.state.engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    activated = api.post(
        f"/api/v1/proposals/{finish.proposal_id}/activate", json={"expected_revision": revision}
    )
    assert activated.status_code == 200, activated.text
    return task, revision, finish.proposal_id, claim


def test_progress_requires_explicit_estimate_and_corrections_are_append_only(api_a, app):
    task = create_task(api_a, app)
    missing = api_a.post(
        f"/api/v1/tasks/{task['id']}/work-logs",
        json={"observed_minutes": 15, "expected_revision": task["revision"]},
    )
    assert missing.status_code == 422
    observed = api_a.post(
        f"/api/v1/tasks/{task['id']}/work-logs",
        json={
            "observed_minutes": 15,
            "new_remaining_minutes": 50,
            "expected_revision": task["revision"],
        },
    )
    assert observed.status_code == 201, observed.text
    corrected = api_a.post(
        f"/api/v1/work-logs/{observed.json()['id']}/corrections",
        json={
            "observed_minutes": 10,
            "new_remaining_minutes": 55,
            "expected_revision": observed.json()["revision"],
        },
    )
    assert corrected.status_code == 201, corrected.text
    assert api_a.get(f"/api/v1/tasks/{task['id']}").json()["remaining_minutes"] == 55
    from planner.db.adaptation_models import WorkLog

    with Session(app.state.engine) as db:
        logs = list(db.scalars(select(WorkLog).order_by(WorkLog.created_at, WorkLog.id)))
        assert len(logs) == 2
        assert {item.observed_minutes for item in logs} == {10, 15}
    with pytest.raises(DBAPIError):
        with app.state.engine.begin() as db:
            db.execute(text("UPDATE work_logs SET observed_minutes=999"))


def test_lock_conflict_requires_explicit_correction_and_move_preserves_proposal(api_a, app):
    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    before = api_a.get(f"/api/v1/proposals/{proposal_id}").json()
    block = before["candidate"]["blocks"][0]
    locked = api_a.post(
        f"/api/v1/blocks/{block['id']}/lock", json={"locked": True, "expected_revision": revision}
    )
    assert locked.status_code == 200, locked.text
    conflict = api_a.post(
        f"/api/v1/tasks/{task['id']}/work-logs",
        json={
            "observed_minutes": 10,
            "new_remaining_minutes": 15,
            "expected_revision": locked.json()["revision"],
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "LOCK_EXCEEDS_REMAINING"
    moved = api_a.post(
        f"/api/v1/blocks/{block['id']}/move",
        json={
            "start": "2026-09-25T11:00Z",
            "end": "2026-09-25T12:00Z",
            "expected_revision": locked.json()["revision"],
        },
    )
    assert moved.status_code == 200, moved.text
    assert api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"] == before["candidate"]


def test_what_if_isolated_preview_then_stale_compare_and_swap_rejected(api_a, app):
    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    before = api_a.get("/api/v1/me").json()["revision"]
    preview = api_a.post(
        "/api/v1/what-ifs",
        json={
            "expected_revision": revision,
            "task_changes": [{"task_id": task["id"], "remaining_minutes": 120}],
        },
    )
    assert preview.status_code == 202, preview.text
    assert api_a.get("/api/v1/me").json()["revision"] == before
    from planner.db.models import PlanningState

    with Session(app.state.engine) as db:
        assert db.get(PlanningState, claim.owner_id).active_proposal_id == proposal_id
    whatif_claim = claim_next(app.state.engine, now=NOW)
    finish = finalize(
        app.state.engine, whatif_claim, greedy_schedule(whatif_claim.snapshot), now=NOW
    )
    assert finish.proposal_id is None
    result = api_a.get("/api/v1/what-ifs/" + preview.json()["id"])
    assert result.json()["state"] == "READY"
    assert sum(b["end_slot"] - b["start_slot"] for b in result.json()["candidate"]["blocks"]) == 8
    edit = api_a.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "Changed while previewing", "expected_revision": revision},
    )
    assert edit.status_code == 200, edit.text
    applied = api_a.post(
        "/api/v1/what-ifs/" + preview.json()["id"] + "/apply", json={"expected_revision": revision}
    )
    assert applied.status_code == 409
    assert applied.json()["code"] == "STALE_REVISION"


def test_completed_work_and_history_survive_correction_without_reusing_completed_block(
    api_a, api_b, app
):
    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    block = api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"]["blocks"][0]
    done = api_a.post(
        f"/api/v1/tasks/{task['id']}/work-logs",
        json={
            "observed_minutes": 60,
            "complete": True,
            "block_id": block["id"],
            "expected_revision": revision,
        },
    )
    assert done.status_code == 201, done.text
    assert api_a.get(f"/api/v1/tasks/{task['id']}").json()["state"] == "DONE"
    denied = api_b.get(f"/api/v1/tasks/{task['id']}/work-logs")
    assert denied.status_code == 404
    locked = api_a.post(
        f"/api/v1/blocks/{block['id']}/lock",
        json={"locked": True, "expected_revision": done.json()["revision"]},
    )
    assert locked.status_code == 409
    correction = api_a.post(
        f"/api/v1/work-logs/{done.json()['id']}/corrections",
        json={
            "observed_minutes": 45,
            "new_remaining_minutes": 15,
            "expected_revision": done.json()["revision"],
        },
    )
    assert correction.status_code == 201, correction.text
    history = api_a.get(f"/api/v1/tasks/{task['id']}/work-logs").json()["items"]
    assert len(history) == 2 and {row["id"] for row in history} == {
        done.json()["id"],
        correction.json()["id"],
    }
    api_a.post("/api/v1/replans", json={"expected_revision": correction.json()["revision"]})
    replanned = claim_next(app.state.engine, now=NOW)
    assert not replanned.snapshot.prior_candidate.blocks


def test_missed_work_does_not_reduce_remaining_and_in_progress_can_activate(api_a, app):
    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    block = api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"]["blocks"][0]
    current = NOW + timedelta(minutes=7)
    app.state.clock = lambda: current
    progress = api_a.post(
        f"/api/v1/blocks/{block['id']}/lock",
        json={
            "locked": False,
            "in_progress": True,
            "expected_end": (NOW + timedelta(minutes=30)).isoformat(),
            "expected_revision": revision,
        },
    )
    assert progress.status_code == 200, progress.text
    assert api_a.get(f"/api/v1/tasks/{task['id']}").json()["remaining_minutes"] == 60
    api_a.post("/api/v1/replans", json={"expected_revision": progress.json()["revision"]})
    next_claim = claim_next(app.state.engine, now=current)
    result = finalize(
        app.state.engine, next_claim, greedy_schedule(next_claim.snapshot), now=current
    )
    assert result.proposal_id, result
    app.state.clock = lambda: current + timedelta(minutes=10)
    selected = api_a.post(
        f"/api/v1/proposals/{result.proposal_id}/activate",
        json={"expected_revision": progress.json()["revision"]},
    )
    assert selected.status_code == 200, selected.text
    protected = api_a.get("/api/v1/protected-work").json()["items"]
    assert protected[0]["id"] == block["id"] and protected[0]["source"] == "IN_PROGRESS"


def test_reviewed_preview_applies_once_and_never_publishes_preview(api_a, app):
    from planner.db.job_models import ProposalRecord, PublicationOperation

    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    preview = api_a.post(
        "/api/v1/what-ifs",
        json={
            "expected_revision": revision,
            "task_changes": [{"task_id": task["id"], "remaining_minutes": 120}],
        },
    ).json()
    with Session(app.state.engine) as db:
        before = db.scalar(select(func.count()).select_from(PublicationOperation))
    preview_claim = claim_next(app.state.engine, now=NOW)
    finalize(app.state.engine, preview_claim, greedy_schedule(preview_claim.snapshot), now=NOW)
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PublicationOperation)) == before
        assert db.scalar(select(func.count()).select_from(ProposalRecord)) == 1
    applied = api_a.post(
        "/api/v1/what-ifs/" + preview["id"] + "/apply", json={"expected_revision": revision}
    )
    assert applied.status_code == 200, applied.text
    assert api_a.get(f"/api/v1/tasks/{task['id']}").json()["remaining_minutes"] == 120
    competing = api_a.post(
        "/api/v1/what-ifs/" + preview["id"] + "/apply", json={"expected_revision": revision}
    )
    assert competing.status_code == 409
    from planner.db.models import PendingReplan, PlanningState

    with Session(app.state.engine) as db:
        state = db.get(PlanningState, claim.owner_id)
        assert state.revision == revision + 1 and state.active_proposal_id == proposal_id
        assert db.get(PendingReplan, claim.owner_id).desired_revision == revision + 1


def test_invalid_feasible_preview_cannot_apply(api_a, app):
    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    preview = api_a.post(
        "/api/v1/what-ifs",
        json={
            "expected_revision": revision,
            "task_changes": [{"task_id": task["id"], "remaining_minutes": 120}],
        },
    ).json()
    preview_claim = claim_next(app.state.engine, now=NOW)
    invalid = greedy_schedule(preview_claim.snapshot).model_copy(update={"blocks": ()})
    finish = finalize(app.state.engine, preview_claim, invalid, now=NOW)
    assert finish.state == "FAILED"
    applied = api_a.post(
        "/api/v1/what-ifs/" + preview["id"] + "/apply", json={"expected_revision": revision}
    )
    assert applied.status_code == 409 and applied.json()["code"] == "PREVIEW_NOT_APPLICABLE"
    assert api_a.get("/api/v1/me").json()["revision"] == revision


def test_two_concurrent_preview_applications_accept_only_one_revision(api_a, app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    previews = []
    for minutes in (90, 120):
        result = api_a.post(
            "/api/v1/what-ifs",
            json={
                "expected_revision": revision,
                "task_changes": [{"task_id": task["id"], "remaining_minutes": minutes}],
            },
        ).json()
        queued = claim_next(app.state.engine, now=NOW)
        finalize(app.state.engine, queued, greedy_schedule(queued.snapshot), now=NOW)
        previews.append(result["id"])
    barrier = Barrier(2)

    def apply(preview_id):
        barrier.wait(timeout=5)
        return api_a.post(
            "/api/v1/what-ifs/" + preview_id + "/apply", json={"expected_revision": revision}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, previews))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert api_a.get("/api/v1/me").json()["revision"] == revision + 1


def test_unobserved_past_work_is_rescheduled_without_reusing_past_block(api_a, app):
    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    old = api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"]["blocks"][0]
    current = NOW + timedelta(hours=2)
    app.state.clock = lambda: current
    api_a.post("/api/v1/replans", json={"expected_revision": revision})
    next_claim = claim_next(app.state.engine, now=current)
    assert next_claim.snapshot.tasks[0].remaining_minutes == 60
    finish = finalize(
        app.state.engine, next_claim, greedy_schedule(next_claim.snapshot), now=current
    )
    proposal = api_a.get(f"/api/v1/proposals/{finish.proposal_id}").json()
    assert all(b["id"] != old["id"] for b in proposal["candidate"]["blocks"])
    assert sum(b["end_slot"] - b["start_slot"] for b in proposal["candidate"]["blocks"]) == 4


def test_multiple_queued_previews_do_not_create_normal_proposals(api_a, app):
    from planner.db.job_models import Job, ProposalRecord

    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    for minutes in (90, 120):
        response = api_a.post(
            "/api/v1/what-ifs",
            json={
                "expected_revision": revision,
                "task_changes": [{"task_id": task["id"], "remaining_minutes": minutes}],
            },
        )
        assert response.status_code == 202
    with Session(app.state.engine) as db:
        queued = list(db.scalars(select(Job).where(Job.state == "QUEUED")))
        assert len(queued) == 2 and all(job.kind == "WHAT_IF" for job in queued)
    for _ in range(2):
        next_claim = claim_next(app.state.engine, now=NOW)
        finalize(app.state.engine, next_claim, greedy_schedule(next_claim.snapshot), now=NOW)
    assert claim_next(app.state.engine, now=NOW) is None
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProposalRecord)) == 1


def test_failed_preview_worker_updates_visible_terminal_state(api_a, app):
    from planner.jobs.handlers import fail_attempt

    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    preview = api_a.post(
        "/api/v1/what-ifs",
        json={
            "expected_revision": revision,
            "task_changes": [{"task_id": task["id"], "remaining_minutes": 120}],
        },
    ).json()
    next_claim = claim_next(app.state.engine, now=NOW)
    fail_attempt(
        app.state.engine, next_claim, now=NOW, reason_code="INVALID_CHILD_RESULT", retryable=False
    )
    result = api_a.get("/api/v1/what-ifs/" + preview["id"])
    assert result.json()["state"] == "FAILED"


def test_move_replan_keeps_identity_and_structured_diff(api_a, app):
    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    block = api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"]["blocks"][0]
    moved = api_a.post(
        f"/api/v1/blocks/{block['id']}/move",
        json={
            "start": "2026-09-25T11:00Z",
            "end": "2026-09-25T12:00Z",
            "expected_revision": revision,
        },
    )
    revision = moved.json()["revision"]
    api_a.post("/api/v1/replans", json={"expected_revision": revision})
    next_claim = claim_next(app.state.engine, now=NOW)
    finish = finalize(app.state.engine, next_claim, greedy_schedule(next_claim.snapshot), now=NOW)
    assert finish.proposal_id, finish
    result = api_a.get(f"/api/v1/proposals/{finish.proposal_id}/diff").json()
    assert len(result["moved"]) == 1 and not result["added"] and not result["removed"]
    assert result["moved"][0]["new"]["id"] == block["id"]
    assert result["moved"][0]["reason_codes"] == ["BLOCK_TIME_CHANGED"]
    # Generating a new proposal does not change the selected active plan.
    assert api_a.get("/api/v1/active-plan").json()["id"] == str(proposal_id)


def test_completed_calendar_commitment_is_not_reserved_again(api_a, app, monkeypatch):
    from planner.jobs.dispatcher import capture_snapshot

    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    block = api_a.get(f"/api/v1/proposals/{proposal_id}").json()["candidate"]["blocks"][0]
    done = api_a.post(
        f"/api/v1/tasks/{task['id']}/work-logs",
        json={"observed_minutes": 60, "complete": True, "expected_revision": revision},
    )
    assert done.status_code == 201
    monkeypatch.setattr(
        "planner.calendar.sync.calendar_inputs",
        lambda *_: (
            [],
            [
                {
                    "id": block["id"],
                    "owner_id": block["owner_id"],
                    "task_id": block["task_id"],
                    "start": block["start"],
                    "end": block["end"],
                    "locked": True,
                    "source": "CALENDAR",
                }
            ],
            set(),
        ),
    )
    with Session(app.state.engine) as db:
        snapshot = capture_snapshot(db, claim.owner_id, NOW)
        assert not snapshot.protected_blocks


def test_whole_task_completion_reopened_by_correction_does_not_reuse_completed_ids(api_a, app):
    from planner.jobs.dispatcher import capture_snapshot

    task, revision, proposal_id, claim = create_selected_plan(api_a, app)
    done = api_a.post(
        f"/api/v1/tasks/{task['id']}/work-logs",
        json={"observed_minutes": 60, "complete": True, "expected_revision": revision},
    )
    correction = api_a.post(
        f"/api/v1/work-logs/{done.json()['id']}/corrections",
        json={
            "observed_minutes": 45,
            "new_remaining_minutes": 15,
            "expected_revision": done.json()["revision"],
        },
    )
    assert correction.status_code == 201, correction.text
    with Session(app.state.engine) as db:
        snapshot = capture_snapshot(db, claim.owner_id, NOW)
        assert not snapshot.prior_candidate.blocks
