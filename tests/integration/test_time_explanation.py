from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import finalize
from planner.solver.greedy import greedy_schedule
from tests.integration.test_adaptation import create_task
from tests.integration.test_jobs import NOW


def test_planning_time_explanation_preserves_original_and_rounding_with_owner_scope(
    api_a, api_b, app
):
    task = create_task(api_a, app)
    available = api_a.put(
        "/api/v1/availability",
        json={
            "windows": [{"start": "2026-09-25T09:07", "end": "2026-09-25T17:02"}],
            "expected_revision": task["revision"],
        },
    ).json()
    job = api_a.post("/api/v1/replans", json={"expected_revision": available["revision"]}).json()
    claim = claim_next(app.state.engine, now=NOW)
    finished = finalize(app.state.engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    path = f"/api/v1/proposals/{finished.proposal_id}/time-inputs"
    view = api_a.get(path)
    assert view.status_code == 200, view.text
    data = view.json()
    rounded = next(r for r in data["rounding_losses"] if r["field"] == "availability.0.start")
    assert rounded["seconds"] == 480
    assert rounded["original"].endswith("09:07:00Z")
    assert rounded["rounded"].endswith("09:15:00Z")
    assert any(v["value"] == "2026-09-25T09:07" for v in data["original_time_inputs"])
    assert api_b.get(path).status_code == 404
    assert api_a.get(f"/api/v1/jobs/{job['job_id']}/time-inputs").json() == data
