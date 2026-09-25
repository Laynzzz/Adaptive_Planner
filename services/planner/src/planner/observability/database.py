"""Database events collect operation classes and durable context, never SQL/values."""

from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

from opentelemetry import trace
from sqlalchemy import delete, event, inspect, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from planner.observability.models import TraceLink
from planner.observability.runtime import current_traceparent, get_telemetry, span


def context_key(kind, owner, identity):
    return f"{kind}:{owner}:{identity}"


@event.listens_for(Session, "before_flush")
def persist_context(db, flush_context, instances):
    parent = current_traceparent()
    if not parent or not getattr(db.get_bind(), "_planner_observed", False):
        return
    from planner.db.ai_models import InterpretationRecord
    from planner.db.calendar_models import CalendarConnection
    from planner.db.job_models import Job
    from planner.db.models import PlanningState

    records = []
    for item in list(db.new) + list(db.dirty):
        if isinstance(item, PlanningState) and item not in db.new:
            if inspect(item).attrs.revision.history.has_changes():
                records.append(("revision", item.owner_id, item.revision))
            if (
                item.active_proposal_id
                and inspect(item).attrs.active_proposal_id.history.has_changes()
            ):
                records.append(("activation", item.owner_id, item.active_proposal_id))
        elif isinstance(item, (Job, InterpretationRecord)):
            if item.id is None:
                item.id = uuid4()
            records.append(
                ("job" if isinstance(item, Job) else "interpretation", item.owner_id, item.id)
            )
        elif isinstance(item, CalendarConnection):
            if item.state == "DISCONNECTING" and inspect(item).attrs.state.history.has_changes():
                records.append(("calendar_disconnect", item.owner_id, item.generation))
            for kind in ("sync", "publish"):
                identity = getattr(item, kind + "_request")
                if identity and inspect(item).attrs[kind + "_request"].history.has_changes():
                    records.append(("calendar_" + kind, item.owner_id, identity))
    for kind, owner, identity in records:
        statement = insert(TraceLink).values(
            key=context_key(kind, owner, identity),
            owner_id=owner,
            traceparent=parent,
            created_at=datetime.now(UTC),
        )
        db.connection().execute(statement.on_conflict_do_nothing(index_elements=[TraceLink.key]))


def load_context(engine, kind, owner, identity):
    with Session(engine) as db:
        return db.scalar(
            select(TraceLink.traceparent).where(
                TraceLink.key == context_key(kind, owner, identity), TraceLink.owner_id == owner
            )
        )


def retain_recent_context(engine, *, now, days=7):
    with engine.begin() as connection:
        return connection.execute(
            delete(TraceLink).where(TraceLink.created_at < now - timedelta(days=days))
        ).rowcount


def instrument_engine(engine):
    if getattr(engine, "_planner_observed", False):
        return engine
    engine._planner_observed = True

    @event.listens_for(engine, "before_cursor_execute")
    def before(connection, cursor, statement, parameters, context, executemany):
        operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "OTHER"
        if operation not in ("SELECT", "INSERT", "UPDATE", "DELETE", "COMMIT", "ROLLBACK"):
            operation = "OTHER"
        manager = None
        if trace.get_current_span().get_span_context().is_valid:
            manager = span("db.query", db_operation=operation)
            manager.__enter__()
        connection.info["planner_query"] = (perf_counter(), operation, manager)

    def finish(connection, error=None):
        pending = connection.info.pop("planner_query", None)
        if pending:
            started, operation, manager = pending
            get_telemetry().measure(
                "planner.db.duration",
                perf_counter() - started,
                operation=operation,
                status="error" if error else "ok",
            )
            if manager:
                manager.__exit__(type(error) if error else None, error, None)

    @event.listens_for(engine, "after_cursor_execute")
    def after(connection, cursor, statement, parameters, context, executemany):
        finish(connection)

    @event.listens_for(engine, "handle_error")
    def failed(context):
        if context.connection:
            finish(context.connection, context.original_exception)

    @event.listens_for(engine, "begin")
    def begun(connection):
        connection.info["planner_transaction_start"] = perf_counter()

    @event.listens_for(engine, "commit")
    def committed(connection):
        started = connection.info.pop("planner_transaction_start", perf_counter())
        get_telemetry().measure(
            "planner.db.transaction.duration", perf_counter() - started, status="commit"
        )

    @event.listens_for(engine, "rollback")
    def rolled_back(connection):
        started = connection.info.pop("planner_transaction_start", perf_counter())
        get_telemetry().measure(
            "planner.db.transaction.duration", perf_counter() - started, status="rollback"
        )

    return engine
