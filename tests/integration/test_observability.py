"""Real committed handoffs and fault telemetry without payload capture."""

import json
from uuid import UUID

import pytest
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.ai.worker import run_once
from planner.db.models import PlanningState
from planner.observability.database import load_context
from planner.observability.runtime import Telemetry, span, use


@pytest.fixture
def recorder(app):
    exporter = InMemorySpanExporter()
    metrics = InMemoryMetricReader()
    telemetry = Telemetry(exporter=exporter, metric_reader=metrics)
    app.state.telemetry = telemetry
    yield telemetry, exporter, metrics
    telemetry.shutdown()


def test_api_committed_job_worker_provider_trace_and_redaction(api_a, app, recorder):
    telemetry, exporter, _ = recorder
    response = api_a.post(
        "/api/v1/interpretations",
        json={
            "text": "PRIVATE_SYNTHETIC study for 60 minutes due 2026-10-01",
            "mode": "mock",
            "expected_revision": 0,
        },
    )
    assert response.status_code == 202, response.text
    identity = UUID(response.json()["id"])
    owner = UUID(api_a.get("/api/v1/me").json()["id"])
    parent = load_context(app.state.engine, "interpretation", owner, identity)
    assert parent is not None
    with use(telemetry):
        assert run_once(app.state.engine)
    spans = exporter.get_finished_spans()
    worker = next(s for s in spans if s.name == "job.interpret")
    provider = next(s for s in spans if s.name == "provider.call")
    api = next(
        s
        for s in spans
        if s.name == "api.request" and s.context.trace_id == worker.context.trace_id
    )
    assert worker.parent.span_id == api.context.span_id
    assert provider.parent.span_id == worker.context.span_id
    assert worker.attributes["job.state"] == "READY"
    serialized = json.dumps([s.to_json() for s in spans])
    assert "PRIVATE_SYNTHETIC" not in serialized
    assert "local-demo" not in serialized and "csrf_token" not in serialized
    assert any(s.name == "db.query" for s in spans)


def test_context_rolls_back_with_business_transaction(api_a, app, recorder):
    telemetry, _, _ = recorder
    owner = UUID(api_a.get("/api/v1/me").json()["id"])
    with use(telemetry), span("api.request"):
        with pytest.raises(RuntimeError):
            with Session(app.state.engine) as db, db.begin():
                state = db.get(PlanningState, owner, with_for_update=True)
                state.revision = 777
                db.flush()
                assert load_context(db.connection(), "revision", owner, 777)
                raise RuntimeError("SYNTHETIC rollback")
    assert load_context(app.state.engine, "revision", owner, 777) is None
    with Session(app.state.engine) as db:
        assert db.scalar(select(PlanningState.revision).where(PlanningState.owner_id == owner)) == 0
