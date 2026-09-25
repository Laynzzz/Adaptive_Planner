import json

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_trace_redaction_and_exception_safety():
    from planner.observability.runtime import Telemetry, span, use

    exporter = InMemorySpanExporter()
    telemetry = Telemetry(exporter=exporter)
    with use(telemetry):
        with pytest.raises(RuntimeError):
            with span(
                "provider.call",
                provider_kind="mock",
                provider_operation="extract",
                prompt="PRIVATE PROMPT",
                authorization="Bearer PRIVATE TOKEN",
            ):
                raise RuntimeError("PRIVATE CALENDAR TITLE and oauth_code=SECRET")
    records = exporter.get_finished_spans()
    assert len(records) == 1
    serialized = json.dumps([r.to_json() for r in records])
    assert "PRIVATE" not in serialized and "SECRET" not in serialized
    assert records[0].attributes["error.type"] == "RuntimeError"
    assert records[0].attributes["provider.kind"] == "mock"
    telemetry.shutdown()


def test_metric_dimensions_reject_identity_and_payload_labels():
    from planner.observability.runtime import Telemetry

    telemetry = Telemetry(exporter=InMemorySpanExporter())
    with pytest.raises(ValueError, match="metric dimension"):
        telemetry.measure("job.duration", 0.2, owner_id="private-owner")
    with pytest.raises(ValueError, match="metric dimension"):
        telemetry.measure("job.duration", 0.2, job_id="1234")
    telemetry.measure("job.duration", 0.2, stage="solve", status="SUCCEEDED")
    telemetry.shutdown()


def test_child_route_observation_returns_to_parent_without_payload():
    from planner.jobs.subprocesses import run_solver
    from planner.observability.runtime import Telemetry, span, use
    from tests.fixtures.builders import snapshot

    exporter = InMemorySpanExporter()
    telemetry = Telemetry(exporter=exporter)
    with use(telemetry), span("job.solve"):
        result = run_solver(snapshot())
    assert result.candidate is not None
    route = next(s for s in exporter.get_finished_spans() if s.name == "solver.route")
    assert route.attributes["routing.mode"] == "fixed"
    assert route.attributes["routing.decision"] == "CP_SAT"
    assert "synthetic draft" not in route.to_json()
    telemetry.shutdown()
