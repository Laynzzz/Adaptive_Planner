"""Manual OpenTelemetry instrumentation with explicit redaction boundaries.

Never record exception messages, stack traces, SQL, URLs, headers, or arguments.
Operation UUIDs may link spans; metric dimensions are a separate bounded allowlist.
"""

import inspect
import json
import logging
import math
import os
import sys
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter

from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Link, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_current = ContextVar("planner_telemetry", default=None)
_process = None
_lock = threading.Lock()
_propagator = TraceContextTextMapPropagator()
_allowed_attributes = {
    "operation.id",
    "routing.mode",
    "routing.decision",
    "routing.fallback",
    "job.kind",
    "job.state",
    "solver.status",
    "reason.code",
    "db.operation",
    "http.route",
    "http.method",
    "http.status_code",
    "provider.kind",
    "provider.operation",
    "result.status",
    "task.count",
    "block.count",
    "error.type",
    "attempt.count",
    "model.input_tokens",
    "model.output_tokens",
    "model.cost_microusd",
}
_dimensions = {"stage", "status", "operation", "provider", "route", "method"}
_span_names = {
    "api.request",
    "db.query",
    "db.transaction",
    "job.solve",
    "job.interpret",
    "job.calendar",
    "provider.call",
    "job.result",
    "incident.recovery",
    "solver.route",
}


def safe_attributes(values):
    result = {}
    for key, value in values.items():
        normalized = key.replace("_", ".") if "." not in key else key
        # Underscores within semantic names are intentional.
        normalized = {
            "http.status.code": "http.status_code",
            "model.input.tokens": "model.input_tokens",
            "model.output.tokens": "model.output_tokens",
            "model.cost.microusd": "model.cost_microusd",
        }.get(normalized, normalized)
        if normalized not in _allowed_attributes or value is None:
            continue
        if isinstance(value, str):
            result[normalized] = value[:160]
        elif isinstance(value, (bool, int)) or isinstance(value, float) and math.isfinite(value):
            result[normalized] = value
    return result


class RedactedJsonExporter(SpanExporter):
    def __init__(self):
        self.logger = logging.getLogger("planner.telemetry")
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.__stderr__)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def export(self, spans):
        for item in spans:
            self.logger.info(
                json.dumps(
                    {
                        "event": "span",
                        "name": item.name,
                        "trace_id": format(item.context.trace_id, "032x"),
                        "span_id": format(item.context.span_id, "016x"),
                        "parent_span_id": format(item.parent.span_id, "016x")
                        if item.parent
                        else None,
                        "start_unix_ns": item.start_time,
                        "end_unix_ns": item.end_time,
                        "status": item.status.status_code.name,
                        "attributes": safe_attributes(dict(item.attributes or {})),
                    },
                    separators=(",", ":"),
                )
            )
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


class Telemetry:
    def __init__(
        self,
        *,
        exporter=None,
        metric_reader=None,
        sample_ratio=1.0,
        service_name="adaptive-planner",
    ):
        resource = Resource.create({"service.name": service_name, "service.version": "0.1.0"})
        self.provider = TracerProvider(
            resource=resource, sampler=ParentBased(TraceIdRatioBased(sample_ratio))
        )
        self.provider.add_span_processor(
            SimpleSpanProcessor(exporter)
            if exporter is not None
            else BatchSpanProcessor(
                RedactedJsonExporter(),
                max_queue_size=512,
                max_export_batch_size=64,
                schedule_delay_millis=1000,
            )
        )
        endpoint = os.environ.get("PLANNER_OTLP_ENDPOINT")
        readers = [metric_reader] if metric_reader else []
        if endpoint and exporter is None:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

            self.provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=3),
                    max_queue_size=512,
                    max_export_batch_size=64,
                )
            )
            readers.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=endpoint.rstrip("/") + "/v1/metrics", timeout=3),
                    export_interval_millis=10000,
                )
            )
        self.tracer = self.provider.get_tracer("planner.manual")
        self.meter_provider = MeterProvider(
            resource=resource,
            metric_readers=readers,
            views=[
                View(
                    instrument_name="*duration",
                    aggregation=ExplicitBucketHistogramAggregation(
                        boundaries=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30)
                    ),
                )
            ],
        )
        self.meter = self.meter_provider.get_meter("planner.manual")
        self.instruments = {}
        self.instrument_lock = threading.Lock()
        self.observed_engine = None

    def measure(self, name, value, **dimensions):
        if set(dimensions) - _dimensions:
            raise ValueError("Unbounded metric dimension is forbidden")
        if any(not isinstance(v, str) or len(v) > 160 for v in dimensions.values()):
            raise ValueError("Invalid metric dimension")
        with self.instrument_lock:
            instrument = self.instruments.get(name)
            if instrument is None:
                instrument = self.meter.create_histogram(
                    name, unit="s" if name.endswith("duration") else "1"
                )
                self.instruments[name] = instrument
        instrument.record(value, dimensions)

    def observe_database(self, engine):
        # One process owns one database. Tests can supply an isolated Telemetry.
        if self.observed_engine is None:
            from planner.observability.state import register_state_metrics

            self.observed_engine = engine
            register_state_metrics(self, engine)

    def shutdown(self):
        self.provider.force_flush(timeout_millis=3000)
        self.provider.shutdown()
        self.meter_provider.shutdown()


def get_telemetry():
    current = _current.get()
    if current is not None:
        return current
    global _process
    if _process is None:
        with _lock:
            if _process is None:
                _process = Telemetry(
                    sample_ratio=float(os.environ.get("PLANNER_TRACE_SAMPLE_RATIO", "0.1")),
                    service_name=os.environ.get("PLANNER_SERVICE_NAME", "adaptive-planner"),
                )
    return _process


@contextmanager
def use(telemetry):
    token = _current.set(telemetry)
    try:
        yield telemetry
    finally:
        _current.reset(token)


@contextmanager
def span(name, *, parent=None, links=(), **attributes):
    if name not in _span_names:
        raise ValueError("Unknown bounded span name")
    telemetry = get_telemetry()
    context = _propagator.extract({"traceparent": parent}) if parent else None
    started = perf_counter()
    status = "ok"
    with telemetry.tracer.start_as_current_span(
        name,
        context=context,
        links=[
            Link(
                trace.get_current_span(
                    _propagator.extract({"traceparent": link})
                ).get_span_context()
            )
            for link in links
            if link
        ],
        attributes=safe_attributes(attributes),
        record_exception=False,
        set_status_on_exception=False,
    ) as current:
        try:
            yield current
        except BaseException as error:
            status = "error"
            current.set_attribute("error.type", type(error).__name__)
            current.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            telemetry.measure(
                "planner.stage.duration", perf_counter() - started, stage=name, status=status
            )


def current_traceparent():
    carrier = {}
    _propagator.inject(carrier)
    return carrier.get("traceparent")


class ObservedProvider:
    def __init__(self, provider, kind):
        self.provider, self.kind = (
            provider,
            kind if kind in ("mock", "google", "openai") else "other",
        )

    def __getattr__(self, name):
        method = getattr(self.provider, name)
        if name not in (
            "extract",
            "list_events",
            "get_event",
            "create_event",
            "update_event",
            "delete_event",
        ):
            return method
        if inspect.iscoroutinefunction(method):

            @wraps(method)
            async def asynchronous(*args, **kwargs):
                with span("provider.call", provider_kind=self.kind, provider_operation=name):
                    return await method(*args, **kwargs)

            return asynchronous

        @wraps(method)
        def synchronous(*args, **kwargs):
            with span("provider.call", provider_kind=self.kind, provider_operation=name):
                return method(*args, **kwargs)

        return synchronous


def observed_provider(provider, kind=None):
    if isinstance(provider, ObservedProvider):
        return provider
    kind = kind or {
        "FakeCalendarProvider": "mock",
        "DurableMockProvider": "mock",
        "GoogleCalendarProvider": "google",
        "MockProvider": "mock",
        "OpenAIResponsesProvider": "openai",
    }.get(type(provider).__name__, "other")
    return ObservedProvider(provider, kind)


def traced_work(kind):
    def decorate(function):
        @wraps(function)
        def run(engine, claim, *args, **kwargs):
            from planner.observability.database import load_context

            identity = claim.job_id if kind == "solve" else claim.id
            parent = load_context(
                engine, "job" if kind == "solve" else "interpretation", claim.owner_id, identity
            )
            revision_parent = (
                load_context(engine, "revision", claim.owner_id, claim.snapshot.planning_revision)
                if kind == "solve"
                else None
            )
            with span(
                "job.solve" if kind == "solve" else "job.interpret",
                parent=parent or revision_parent,
                links=[revision_parent] if parent else (),
                operation_id=str(identity),
                job_kind=kind,
            ) as current:
                result = function(engine, claim, *args, **kwargs)
                state = getattr(result, "state", "SUCCEEDED" if result else "FENCED")
                if kind != "solve":
                    from sqlalchemy.orm import Session

                    from planner.db.ai_models import InterpretationRecord

                    with Session(engine) as db:
                        record = db.get(InterpretationRecord, identity)
                        if record:
                            state = record.state
                            if record.error_code:
                                current.set_attribute("reason.code", record.error_code)
                            for field in ("input_tokens", "output_tokens", "cost_microusd"):
                                value = record.metadata_json.get(field)
                                if isinstance(value, int) and value >= 0:
                                    current.set_attribute("model." + field, value)
                                    get_telemetry().measure(
                                        "planner.model." + field, value, provider=claim.mode
                                    )
                current.set_attribute("job.state", str(state))
                if state == "FAILED":
                    current.set_status(Status(StatusCode.ERROR))
                reason = getattr(result, "reason_code", None)
                if reason:
                    current.set_attribute("reason.code", reason)
                get_telemetry().measure("planner.jobs.results", 1, stage=kind, status=str(state))
                return result

        return run

    return decorate


def traced_owner_work(kind):
    def decorate(function):
        @wraps(function)
        def run(engine, owner_id, provider, *args, **kwargs):
            from sqlalchemy.orm import Session

            from planner.db.calendar_models import CalendarConnection
            from planner.db.models import PlanningState
            from planner.observability.database import load_context

            with Session(engine) as db:
                connection = db.get(CalendarConnection, owner_id)
                identity = (
                    (
                        connection.generation
                        if kind == "disconnect"
                        else getattr(connection, kind + "_request")
                    )
                    if connection
                    else None
                )
                active = db.get(PlanningState, owner_id).active_proposal_id
            parent = (
                load_context(engine, "calendar_" + kind, owner_id, identity)
                if identity is not None
                else None
            )
            if parent is None and kind == "publish" and active:
                parent = load_context(engine, "activation", owner_id, active)
            with span(
                "job.calendar",
                parent=parent,
                job_kind=kind,
                operation_id=str(identity or active or ""),
            ) as current:
                result = function(engine, owner_id, observed_provider(provider), *args, **kwargs)
                state = getattr(result, "state", result if isinstance(result, str) else "DONE")
                current.set_attribute("result.status", str(state))
                get_telemetry().measure(
                    "planner.calendar.results", 1, stage=kind, status=str(state)
                )
                return result

        return run

    return decorate
