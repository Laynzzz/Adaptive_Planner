"""Low-cardinality queue/lease/provider health gauges from durable state."""

import threading
from datetime import UTC, datetime
from time import monotonic

from opentelemetry.metrics import Observation
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def register_state_metrics(telemetry, engine):
    from planner.db.ai_models import AISpendBudget, InterpretationRecord
    from planner.db.calendar_models import (
        CalendarConflict,
        CalendarConnection,
        CalendarWriteOperation,
    )
    from planner.db.job_models import Job
    from planner.db.models import PendingReplan

    cache = {"at": -10, "values": {}}
    lock = threading.Lock()

    def snapshot():
        with lock:
            if monotonic() - cache["at"] < 5:
                return cache["values"]
            now = datetime.now(UTC)
            values = {}
            try:
                with Session(engine) as db:
                    values["planner.jobs.by_state"] = [
                        Observation(count, {"status": state})
                        for state, count in db.execute(
                            select(Job.state, func.count()).group_by(Job.state)
                        )
                    ]
                    oldest = db.scalar(select(func.min(PendingReplan.enqueued_at)))
                    values["planner.queue.oldest_age"] = [
                        Observation(max(0, (now - oldest).total_seconds()) if oldest else 0)
                    ]
                    values["planner.jobs.expired_leases"] = [
                        Observation(
                            db.scalar(
                                select(func.count())
                                .select_from(Job)
                                .where(Job.state == "RUNNING", Job.lease_until < now)
                            )
                        )
                    ]
                    for metric, code in (
                        ("planner.jobs.stale", "STALE_REVISION"),
                        ("planner.jobs.validator_rejected", "INVALID_CANDIDATE"),
                        ("planner.jobs.lease_lost", "LEASE_EXPIRED"),
                    ):
                        values[metric] = [
                            Observation(
                                db.scalar(
                                    select(func.count())
                                    .select_from(Job)
                                    .where(
                                        Job.state == "SUPERSEDED"
                                        if code == "STALE_REVISION"
                                        else Job.reason_code == code
                                    )
                                )
                            )
                        ]
                    values["planner.calendar.conflicts"] = [
                        Observation(
                            db.scalar(
                                select(func.count())
                                .select_from(CalendarConflict)
                                .where(CalendarConflict.state == "OPEN")
                            )
                        )
                    ]
                    values["planner.calendar.operations"] = [
                        Observation(count, {"status": state})
                        for state, count in db.execute(
                            select(CalendarWriteOperation.state, func.count()).group_by(
                                CalendarWriteOperation.state
                            )
                        )
                    ]
                    last = db.scalar(
                        select(func.min(CalendarConnection.last_sync_at)).where(
                            CalendarConnection.state == "CONNECTED"
                        )
                    )
                    values["planner.calendar.lag"] = [
                        Observation(max(0, (now - last).total_seconds()) if last else 0)
                    ]
                    values["planner.model.proposals"] = [
                        Observation(count, {"status": state})
                        for state, count in db.execute(
                            select(InterpretationRecord.state, func.count()).group_by(
                                InterpretationRecord.state
                            )
                        )
                    ]
                    values["planner.model.invalid"] = [
                        Observation(
                            db.scalar(
                                select(func.count())
                                .select_from(InterpretationRecord)
                                .where(InterpretationRecord.error_code == "MODEL_OUTPUT_INVALID")
                            )
                        )
                    ]
                    budget = db.get(AISpendBudget, "openai")
                    values["planner.model.spend_microusd"] = [
                        Observation(budget.spent_microusd if budget else 0)
                    ]
                    values["planner.model.reserved_microusd"] = [
                        Observation(budget.reserved_microusd if budget else 0)
                    ]
                values["planner.db.reachable"] = [Observation(1)]
            except SQLAlchemyError:
                values = {"planner.db.reachable": [Observation(0)]}
            values["planner.db.pool_in_use"] = [
                Observation(engine.pool.checkedout() if hasattr(engine.pool, "checkedout") else 0)
            ]
            cache.update(at=monotonic(), values=values)
            return values

    names = (
        "planner.jobs.by_state",
        "planner.queue.oldest_age",
        "planner.jobs.expired_leases",
        "planner.jobs.stale",
        "planner.jobs.validator_rejected",
        "planner.jobs.lease_lost",
        "planner.calendar.conflicts",
        "planner.calendar.operations",
        "planner.calendar.lag",
        "planner.model.proposals",
        "planner.model.invalid",
        "planner.model.spend_microusd",
        "planner.model.reserved_microusd",
        "planner.db.reachable",
        "planner.db.pool_in_use",
    )
    for name in names:

        def observe(options, metric=name):
            return snapshot().get(metric, [])

        telemetry.meter.create_observable_gauge(
            name, callbacks=[observe], unit="s" if name.endswith(("age", "lag")) else ""
        )
    return snapshot
