"""Real authenticated queue/review/acceptance boundaries."""

from uuid import uuid4

import pytest

from planner.ai.worker import run_once


def enqueue(api, text, mode="mock"):
    return api.post(
        "/api/v1/interpretations", json={"text": text, "mode": mode, "expected_revision": 0}
    )


def test_queue_is_durable_and_output_alone_cannot_change_tasks(api_a, app):
    queued = enqueue(api_a, "Study algebra for 60 minutes due 2026-09-28")
    assert queued.status_code == 202, queued.text
    id = queued.json()["id"]
    assert api_a.get("/api/v1/tasks").json()["items"] == []
    assert run_once(app.state.engine)
    proposal = api_a.get(f"/api/v1/interpretations/{id}").json()
    assert proposal["state"] == "READY"
    assert api_a.get("/api/v1/tasks").json()["items"] == []
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_unresolved_deadline_requires_review_and_acceptance_is_atomic(api_a, api_b, app):
    id = enqueue(api_a, "Study algebra for 60 minutes due next Thursday").json()["id"]
    run_once(app.state.engine)
    view = api_a.get(f"/api/v1/interpretations/{id}").json()
    assert "tasks.task_1.deadline" in view["proposal"]["unresolved_fields"]
    path = f"/api/v1/interpretations/{id}/accept"
    body = {
        "expected_revision": 0,
        "selected_task_keys": ["task_1"],
        "confirmed_fields": ["tasks.task_1.priority"],
        "overrides": {},
    }
    bad = api_a.post(path, json=body)
    assert bad.status_code == 422
    assert bad.json()["code"] == "CLARIFICATION_REQUIRED"
    assert api_a.get("/api/v1/me").json()["revision"] == 0
    assert api_b.get(f"/api/v1/interpretations/{id}").status_code == 404
    body["overrides"] = {
        "tasks.task_1.deadline": {"kind": "DATE", "value": "2026-10-01", "timezone": "UTC"}
    }
    key = str(uuid4())
    accepted = api_a.post(path, json=body, headers={"Idempotency-Key": key})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["revision"] == 1
    assert len(api_a.get("/api/v1/tasks").json()["items"]) == 1
    assert api_a.post(path, json=body, headers={"Idempotency-Key": key}).json() == accepted.json()


def test_one_active_interpretation_and_disabled_provider_preserve_manual_forms(api_a, app):
    queued = enqueue(api_a, "Study for 60 minutes", mode="openai")
    assert queued.status_code == 202
    assert enqueue(api_a, "Second for 30 minutes").status_code == 409
    run_once(app.state.engine)
    view = api_a.get("/api/v1/interpretations/" + queued.json()["id"]).json()
    assert view["state"] == "FAILED" and view["error_code"] == "LIVE_DISABLED"
    assert (
        api_a.post(
            "/api/v1/tasks",
            json={"expected_revision": 0, "title": "Manual fallback", "remaining_minutes": 60},
        ).status_code
        == 201
    )


def test_weekday_constraints_are_never_silently_accepted(api_a, app):
    id = enqueue(api_a, "Study for 60 minutes\ncannot work Friday").json()["id"]
    run_once(app.state.engine)
    response = api_a.post(
        f"/api/v1/interpretations/{id}/accept",
        json={
            "expected_revision": 0,
            "selected_task_keys": ["task_1"],
            "confirmed_fields": ["tasks.task_1.deadline", "tasks.task_1.priority"],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CONSTRAINT_REVIEW_REQUIRED"
    assert api_a.get("/api/v1/tasks").json()["items"] == []


class OutputProvider:
    def __init__(self, payload):
        self.payload = payload

    async def extract(self, context):
        from planner.ai.provider import LLMResult

        return LLMResult(self.payload, "fake", "test-only", 0)


def test_malformed_or_cyclic_provider_output_never_becomes_ready(api_a, app):
    import json

    from tests.unit.test_interpretation import draft

    for payload in (
        "not json",
        json.dumps({**draft(), "tasks": [{**draft()["tasks"][0], "predecessor_keys": ["task_1"]}]}),
    ):
        id = enqueue(api_a, "Study for 60 minutes").json()["id"]
        run_once(app.state.engine, provider=OutputProvider(payload))
        view = api_a.get(f"/api/v1/interpretations/{id}").json()
        assert view["state"] == "FAILED"
        assert view["error_code"] == "MODEL_OUTPUT_INVALID"
    assert api_a.get("/api/v1/tasks").json()["items"] == []
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_guessed_duration_requires_confirmation_and_stale_batch_is_rejected(api_a, app):
    import json

    from tests.unit.test_interpretation import draft

    value = draft()
    value["tasks"][0]["remaining_minutes"]["label"] = "inferred"
    value["tasks"][0]["remaining_minutes"]["requires_confirmation"] = True
    id = enqueue(api_a, "Study").json()["id"]
    run_once(app.state.engine, provider=OutputProvider(json.dumps(value)))
    path = f"/api/v1/interpretations/{id}/accept"
    body = {
        "expected_revision": 0,
        "selected_task_keys": ["task_1"],
        "confirmed_fields": ["tasks.task_1.priority"],
        "overrides": {"tasks.task_1.deadline": None},
    }
    assert api_a.post(path, json=body).json()["code"] == "CONFIRMATION_REQUIRED"
    assert (
        api_a.post(
            "/api/v1/tasks",
            json={"expected_revision": 0, "title": "Manual", "remaining_minutes": 30},
        ).status_code
        == 201
    )
    body["expected_revision"] = 1
    assert api_a.post(path, json=body).json()["code"] == "STALE_INTERPRETATION"
    assert len(api_a.get("/api/v1/tasks").json()["items"]) == 1


def test_worker_timeout_and_expired_claim_cannot_publish_late(api_a, app):
    import asyncio
    from datetime import timedelta

    from planner.ai.provider import AIConfig
    from planner.ai.worker import claim_next, process_claim, reconcile_expired, utc_now

    class Slow:
        async def extract(self, context):
            await asyncio.sleep(1)

    id = enqueue(api_a, "Study").json()["id"]
    run_once(app.state.engine, provider=Slow(), config=AIConfig(provider_timeout_seconds=0.01))
    assert api_a.get(f"/api/v1/interpretations/{id}").json()["error_code"] == "PROVIDER_TIMEOUT"
    id = enqueue(api_a, "Study for 60 minutes").json()["id"]
    now = utc_now()
    claim = claim_next(app.state.engine, now)
    assert reconcile_expired(app.state.engine, now + timedelta(seconds=36)) == 1
    assert not process_claim(app.state.engine, claim)
    assert api_a.get(f"/api/v1/interpretations/{id}").json()["error_code"] == "WORKER_INTERRUPTED"


def test_spend_is_reserved_before_provider_and_unknown_cost_is_conservative(api_a, app):
    from uuid import UUID

    from sqlalchemy.orm import Session

    from planner.ai.provider import AIConfig, ProviderError
    from planner.db.ai_models import AISpendBudget, AISpendReservation

    class Unavailable:
        calls = 0

        async def extract(self, context):
            self.calls += 1
            with Session(app.state.engine) as db:
                assert db.get(AISpendReservation, UUID(id)).amount_microusd > 0
            raise ProviderError("PROVIDER_UNAVAILABLE")

    config = AIConfig(
        live_enabled=True,
        api_key="synthetic-test-only",
        model="test-model",
        approval_reference="test-only",
        budget_microusd=1,
        input_rate_microusd_per_million=1000000,
        output_rate_microusd_per_million=1000000,
        price_as_of="2026-09-25",
    )
    fake = Unavailable()
    id = enqueue(api_a, "Study", mode="openai").json()["id"]
    run_once(app.state.engine, provider=fake, config=config)
    assert fake.calls == 0
    assert api_a.get(f"/api/v1/interpretations/{id}").json()["error_code"] == "SPEND_LIMIT"
    config.budget_microusd = 1000000
    id = enqueue(api_a, "Study", mode="openai").json()["id"]
    run_once(app.state.engine, provider=fake, config=config)
    view = api_a.get(f"/api/v1/interpretations/{id}").json()
    assert fake.calls == 1 and view["state"] == "FAILED"
    assert view["metadata"]["cost_microusd"] is None
    with Session(app.state.engine) as db:
        reservation = db.get(AISpendReservation, UUID(id))
        budget = db.get(AISpendBudget, "openai")
        assert budget.reserved_microusd == 0
        assert budget.spent_microusd == reservation.amount_microusd
        assert not reservation.actual_cost_known


def test_unresolved_global_contradiction_cannot_be_accepted(api_a, app):
    import json

    from tests.unit.test_interpretation import draft

    value = draft()
    value["unresolved_fields"].append("conflicting_request")
    id = enqueue(api_a, "Study").json()["id"]
    run_once(app.state.engine, provider=OutputProvider(json.dumps(value)))
    response = api_a.post(
        f"/api/v1/interpretations/{id}/accept",
        json={
            "expected_revision": 0,
            "selected_task_keys": ["task_1"],
            "confirmed_fields": ["tasks.task_1.priority"],
            "overrides": {"tasks.task_1.deadline": None},
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CLARIFICATION_REQUIRED"
    assert api_a.get("/api/v1/tasks").json()["items"] == []


def test_batch_dependency_acceptance_commits_once_and_invalid_override_rolls_back(api_a, app):
    text = "Study for 30 minutes\nOutline for 30 minutes after task_1"
    id = enqueue(api_a, text).json()["id"]
    run_once(app.state.engine)
    body = {
        "expected_revision": 0,
        "selected_task_keys": ["task_1", "task_2"],
        "confirmed_fields": [
            f"tasks.task_{i}.{name}" for i in (1, 2) for name in ("deadline", "priority")
        ],
        "overrides": {"tasks.task_2.remaining_minutes": -1},
    }
    path = f"/api/v1/interpretations/{id}/accept"
    assert api_a.post(path, json=body).status_code == 422
    assert api_a.get("/api/v1/tasks").json()["items"] == []
    assert api_a.get("/api/v1/me").json()["revision"] == 0
    body["overrides"] = {}
    accepted = api_a.post(path, json=body)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["revision"] == 1
    tasks = api_a.get("/api/v1/tasks").json()["items"]
    assert len(tasks) == 2
    outline = next(task for task in tasks if task["title"] == "Outline")
    assert outline["predecessor_ids"] == [accepted.json()["task_ids"][0]]


@pytest.mark.parametrize("attack", ["invented_hard_busy", "invented_no_deadline", "soft_to_hard"])
def test_adversarial_hard_constraints_suite_rejects_every_acceptance(api_a, app, attack):
    import json

    from tests.unit.test_interpretation import draft

    value = draft()
    source = "Study" if attack != "soft_to_hard" else "Study dislike Friday"
    evidence = {"start": 0, "end": 5, "text": "Study"}
    if attack == "soft_to_hard":
        evidence = {"start": 6, "end": 20, "text": "dislike Friday"}
    value["constraints"] = [
        {
            "key": "constraint_1",
            "kind": "HARD_NO_DEADLINE" if attack == "invented_no_deadline" else "HARD_UNAVAILABLE",
            "weekday": 4,
            "label": "explicit",
            "evidence": [evidence],
            "requires_confirmation": True,
        }
    ]
    id = enqueue(api_a, source).json()["id"]
    run_once(app.state.engine, provider=OutputProvider(json.dumps(value)))
    response = api_a.post(
        f"/api/v1/interpretations/{id}/accept",
        json={
            "expected_revision": 0,
            "selected_task_keys": ["task_1"],
            "confirmed_fields": ["tasks.task_1.priority", "constraints.constraint_1"],
            "selected_constraint_keys": ["constraint_1"],
            "overrides": {"tasks.task_1.deadline": None},
        },
    )
    assert response.status_code in (409, 422)
    assert api_a.get("/api/v1/tasks").json()["items"] == []
    assert api_a.get("/api/v1/me").json()["revision"] == 0


def test_expired_live_claim_cannot_reserve_or_call_provider(api_a, app):
    from datetime import timedelta

    from planner.ai.provider import AIConfig, LLMResult
    from planner.ai.worker import claim_next, process_claim, reconcile_expired, utc_now

    class NeverCall:
        calls = 0

        async def extract(self, context):
            self.calls += 1
            return LLMResult("{}", "fake", "test-only", 0)

    config = AIConfig(
        live_enabled=True,
        api_key="synthetic-test-only",
        model="test-model",
        approval_reference="test-only",
        budget_microusd=1000000,
        input_rate_microusd_per_million=1000000,
        output_rate_microusd_per_million=1000000,
        price_as_of="2026-09-25",
    )
    enqueue(api_a, "Study", mode="openai")
    now = utc_now()
    claim = claim_next(app.state.engine, now)
    assert reconcile_expired(app.state.engine, now + timedelta(seconds=36)) == 1
    fake = NeverCall()
    assert not process_claim(app.state.engine, claim, provider=fake, config=config)
    assert fake.calls == 0


def test_explicitly_reviewed_weekday_rule_only_batch_is_atomic(api_a, app):
    id = enqueue(api_a, 'dislike Friday').json()['id']
    run_once(app.state.engine)
    body = {'expected_revision': 0, 'selected_task_keys': [],
            'selected_constraint_keys': ['constraint_1'], 'confirmed_fields': []}
    path = f'/api/v1/interpretations/{id}/accept'
    assert api_a.post(path, json=body).status_code == 422
    body['confirmed_fields'] = ['constraints.constraint_1']
    accepted = api_a.post(path, json=body)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['task_ids'] == []
    assert len(accepted.json()['weekday_rule_ids']) == 1
    assert api_a.get('/api/v1/me').json()['revision'] == 1


def test_conflicting_selected_task_and_no_deadline_rule_roll_back_together(api_a, app):
    id = enqueue(api_a, 'Study for 60 minutes due 2026-10-02\nno deadlines Friday').json()['id']
    run_once(app.state.engine)
    response = api_a.post(f'/api/v1/interpretations/{id}/accept', json={
        'expected_revision': 0, 'selected_task_keys': ['task_1'],
        'selected_constraint_keys': ['constraint_1'],
        'confirmed_fields': ['tasks.task_1.priority', 'constraints.constraint_1']})
    assert response.status_code == 409
    assert response.json()['code'] == 'DEADLINE_WEEKDAY_FORBIDDEN'
    assert api_a.get('/api/v1/tasks').json()['items'] == []
    assert api_a.get('/api/v1/me').json()['revision'] == 0
