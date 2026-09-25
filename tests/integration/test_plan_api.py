from uuid import uuid4

from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import finalize
from planner.solver.greedy import greedy_schedule
from tests.integration.test_jobs import NOW


def test_owner_scoped_generate_inspect_activate_and_idempotency(api_a, api_b, app):
    app.state.clock = lambda: NOW
    revision = api_a.get("/api/v1/me").json()["revision"]
    task = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "Draft",
            "remaining_minutes": 60,
            "deadline": {"kind": "TIMESTAMP", "value": "2026-09-25T17:00:00Z"},
            "expected_revision": revision,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert task.status_code == 201, task.text
    revision = task.json()["revision"]
    available = api_a.put(
        "/api/v1/availability",
        json={
            "windows": [{"start": "2026-09-25T09:00Z", "end": "2026-09-25T17:00Z"}],
            "expected_revision": revision,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert available.status_code == 200, available.text
    revision = available.json()["revision"]
    key = str(uuid4())
    request = {"expected_revision": revision}
    generated = api_a.post("/api/v1/replans", json=request, headers={"Idempotency-Key": key})
    assert generated.status_code == 202, generated.text
    assert (
        api_a.post("/api/v1/replans", json=request, headers={"Idempotency-Key": key}).json()
        == generated.json()
    )
    job_id = generated.json()["job_id"]
    assert api_b.get("/api/v1/jobs/" + job_id).status_code == 404
    claim = claim_next(app.state.engine, now=NOW)
    finished = finalize(app.state.engine, claim, greedy_schedule(claim.snapshot), now=NOW)
    job = api_a.get("/api/v1/jobs/" + job_id)
    assert job.json()["state"] == "SUCCEEDED"
    proposal_id = str(finished.proposal_id)
    proposal = api_a.get("/api/v1/proposals/" + proposal_id)
    assert proposal.status_code == 200
    assert len(proposal.json()["candidate"]["blocks"]) > 0
    assert api_b.get("/api/v1/proposals/" + proposal_id).status_code == 404
    assert api_b.get("/api/v1/proposals").json()["items"] == []
    activated = api_a.post(
        "/api/v1/proposals/" + proposal_id + "/activate",
        json=request,
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["state"] == "ACTIVE"
    assert activated.json()["publication_state"] == "PENDING_CONNECTION"
