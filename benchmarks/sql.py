"""Before/after SQL study on disposable PostgreSQL, with correct existing-query baseline."""

import argparse
import hashlib
import json
import platform
import statistics
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from time import perf_counter, process_time
from uuid import uuid4

from sqlalchemy import event, insert, select, text, update
from sqlalchemy.orm import Session

from benchmarks.child import rss_bytes
from benchmarks.storage import CLOCK, isolated_database, seed_storage
from planner.db.job_models import Job
from planner.db.models import DependencyEdge, Identity, Task
from planner.db.queries import task_page_data
from planner.db.repositories import task_data
from planner.jobs.dispatcher import claim_next

INDEX_DDL = [
    (
        "CREATE INDEX ix_tasks_active_page ON "
        "tasks(owner_id,created_at,id) WHERE state IN "
        "('TODO','IN_PROGRESS')"
    ),
    (
        "CREATE INDEX ix_jobs_ready_owner_created ON "
        "jobs(owner_id,created_at) WHERE state IN ('QUEUED','RETRY_WAIT')"
    ),
    "CREATE INDEX ix_jobs_retry_owner_at ON jobs(owner_id,retry_at) WHERE state='RETRY_WAIT'",
]
DISPATCH_SQL = """SELECT s.owner_id FROM user_planning_state s
JOIN pending_replans p ON p.owner_id=s.owner_id
LEFT JOIN owner_dispatch_state d ON d.owner_id=s.owner_id
WHERE NOT EXISTS(SELECT 1 FROM jobs j WHERE j.owner_id=s.owner_id AND j.state='RUNNING')
AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.owner_id=s.owner_id AND j.state='RETRY_WAIT'
 AND j.retry_at > %(now)s AND j.planning_revision=s.revision
 AND j.calendar_revision=s.calendar_revision)
AND (p.explicit OR p.updated_at <= %(debounce)s OR p.enqueued_at <= %(oldest)s)
ORDER BY d.last_dispatch_at ASC NULLS FIRST,p.enqueued_at,s.owner_id
LIMIT 1 FOR UPDATE OF s SKIP LOCKED"""


def distribution(values):
    ordered = sorted(values)
    return {
        "n": len(values),
        "p50": statistics.median(values) if values else None,
        "p95": ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)] if ordered else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def explain(engine, statement, parameters=None):
    with closing(engine.raw_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters)
            result = cursor.fetchone()[0][0]
        connection.rollback()
    return result


def capture_plans(engine, owner):
    query = (
        select(Task)
        .where(Task.owner_id == owner, Task.state == "TODO")
        .order_by(Task.created_at, Task.id)
        .limit(50)
    )
    rendered = str(query.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))
    with Session(engine) as db:
        ids = list(
            db.scalars(
                select(Task.id).where(Task.owner_id == owner, Task.state == "TODO").limit(50)
            )
        )
    edges = select(DependencyEdge).where(
        DependencyEdge.owner_id == owner, DependencyEdge.successor_id.in_(ids)
    )
    edge_sql = str(edges.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))
    ready = (
        "SELECT * FROM jobs WHERE owner_id=%(owner)s AND state IN "
        "('QUEUED','RETRY_WAIT') ORDER BY created_at LIMIT 1 FOR UPDATE"
    )
    return {
        "active_task_page": explain(engine, rendered),
        "dependency_batch": explain(engine, edge_sql),
        "ready_job": explain(engine, ready, {"owner": owner}),
        "dispatch_owner": explain(
            engine,
            DISPATCH_SQL,
            {
                "now": CLOCK,
                "debounce": CLOCK - timedelta(milliseconds=300),
                "oldest": CLOCK - timedelta(seconds=2),
            },
        ),
    }


def read_study(engine, owners, *, batched, repeats):
    latencies, counts = [], []
    observed = []

    def count(connection, cursor, statement, parameters, context, executemany):
        observed.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        for iteration in range(repeats + 5):
            observed.clear()
            start = perf_counter()
            with Session(engine) as db:
                query = select(Task).where(
                    Task.owner_id == owners[iteration % len(owners)], Task.state == "TODO"
                )
                if iteration % 2:
                    # Deterministic follow-on page: the same keyset predicate as the endpoint.
                    query = query.where(Task.created_at > CLOCK + timedelta(seconds=49))
                tasks = db.scalars(query.order_by(Task.created_at, Task.id).limit(50)).all()
                result = (
                    task_page_data(db, tasks)
                    if batched
                    else [task_data(db, task) for task in tasks]
                )
                assert len(result) == len(tasks)
            elapsed = (perf_counter() - start) * 1000
            if iteration >= 5:
                latencies.append(elapsed)
                counts.append(len(observed))
    finally:
        event.remove(engine, "before_cursor_execute", count)
    return {
        "latency_ms": distribution(latencies),
        "queries": distribution(counts),
        "scope": (
            "task SELECT plus dependencies; excludes authentication, watermark and revision queries"
        ),
    }


def write_study(engine, repeats):
    owner = uuid4()
    with engine.begin() as db:
        db.execute(
            insert(Identity),
            {
                "id": owner,
                "issuer": "synthetic-write-probe",
                "subject": str(owner),
                "name": "Write probe",
                "timezone": "UTC",
            },
        )
    tasks = [
        {
            "id": uuid4(),
            "owner_id": owner,
            "title": "Write benchmark",
            "remaining_minutes": 30,
            "priority": 3,
            "state": "TODO",
            "details": {},
            "created_at": CLOCK,
        }
        for _ in range(100)
    ]
    edges = [
        {"owner_id": owner, "predecessor_id": tasks[i - 1]["id"], "successor_id": tasks[i]["id"]}
        for i in range(1, 100)
    ]
    jobs = [
        {
            "id": uuid4(),
            "owner_id": owner,
            "kind": "REPLAN",
            "planning_revision": 0,
            "calendar_revision": 0,
            "state": "QUEUED",
            "fencing_token": 0,
            "attempts": 0,
            "obsolete": False,
            "created_at": CLOCK,
        }
        for _ in range(100)
    ]
    elapsed = []
    for _ in range(repeats):
        start = perf_counter()
        with engine.connect() as db:
            transaction = db.begin()
            db.execute(insert(Task), tasks)
            db.execute(insert(DependencyEdge), edges)
            db.execute(insert(Job), jobs)
            transaction.rollback()
        elapsed.append((perf_counter() - start) * 1000)
    return {
        "transaction_ms": distribution(elapsed),
        "operation": (
            "100 active tasks +99 dependency edges +100 queued jobs inserted and rolled back"
        ),
        "includes_fk_and_index_maintenance": True,
    }


def claim_study(engine, owners, *, claims):
    latencies, advisory, claimed, queue_age, errors = [], [], [], [], []
    local = threading.local()
    lock = threading.Lock()

    def before(connection, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock(712901)" in statement:
            local.lock_start = perf_counter()

    def after(connection, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock(712901)" in statement:
            with lock:
                advisory.append((perf_counter() - local.lock_start) * 1000)

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    started = perf_counter()

    def attempt(_):
        start = perf_counter()
        try:
            claim_now = CLOCK + timedelta(seconds=perf_counter() - started)
            claim = claim_next(engine, now=claim_now, pool_size=2)
            elapsed = (perf_counter() - start) * 1000
            if claim is None:
                return
            with engine.begin() as db:
                created = db.scalar(select(Job.created_at).where(Job.id == claim.job_id))
                db.execute(
                    update(Job)
                    .where(Job.id == claim.job_id)
                    .values(
                        state="FAILED",
                        finished_at=CLOCK,
                        lease_until=None,
                        reason_code="DISPATCH_MEASUREMENT_NO_SOLVER",
                    )
                )
            with lock:
                latencies.append(elapsed)
                claimed.append(str(claim.owner_id))
                queue_age.append((claim_now - created).total_seconds())
        except Exception as error:
            with lock:
                errors.append(type(error).__name__ + ": " + str(error)[:150])

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(attempt, range(claims * 3)))
    finally:
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)
    counts = Counter(claimed)
    elapsed = perf_counter() - started
    return {
        "attempts": claims * 3,
        "empty_polls": claims * 3 - len(claimed) - len(errors),
        "claimed": len(claimed),
        "unique_owners": len(counts),
        "owners": len(owners),
        "claims_per_second": len(claimed) / elapsed,
        "elapsed_seconds": elapsed,
        "latency_ms": distribution(latencies),
        "advisory_statement_ms": distribution(advisory),
        "lock_wait_limit": (
            "advisory statement duration includes round-trip and execution; upper bound on wait"
        ),
        "queue_age_seconds": distribution(queue_age),
        "oldest_pending_age_seconds": max(queue_age, default=0),
        "min_claims_per_owner": min(counts.values(), default=0),
        "max_claims_per_owner": max(counts.values(), default=0),
        "first_cycle_unique_owners": len(set(claimed[: len(owners)])),
        "errors": errors,
        "scope": "real claim/snapshot/lease transactions; no solver or network call under locks",
    }


def refill(engine, owners, round):
    from planner.db.models import PendingReplan

    with engine.begin() as db:
        db.execute(text("UPDATE owner_dispatch_state SET last_dispatch_at=NULL"))
        for i, owner in enumerate(owners):
            db.execute(
                insert(PendingReplan),
                {
                    "owner_id": owner,
                    "desired_revision": 0,
                    "updated_at": CLOCK,
                    "explicit": True,
                    "enqueued_at": CLOCK - timedelta(seconds=len(owners) - i),
                },
            )
            for _ in range(2):
                db.execute(
                    insert(Job),
                    {
                        "id": uuid4(),
                        "owner_id": owner,
                        "kind": "REPLAN",
                        "planning_revision": 0,
                        "calendar_revision": 0,
                        "state": "QUEUED",
                        "fencing_token": 0,
                        "attempts": 0,
                        "obsolete": False,
                        "created_at": CLOCK - timedelta(seconds=len(owners) - i),
                    },
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--compare", action="store_true", required=True)
    args = parser.parse_args()
    spec = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    study_start = perf_counter()
    cpu_start = process_time()
    report = {
        "platform": platform.platform(),
        "cpu_label": "Intel Core i7-13700K,16cores/24logical, shared development host",
        "host_workload": (
            "Concurrent frozen scheduler benchmark2slots and other project "
            "verification; not a dedicated quiet run"
        ),
        "manifest": spec,
        "manifest_hash": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "workloads": {},
    }
    for name, fixture in spec["fixtures"].items():
        with isolated_database() as (engine, database):
            # Fresh HEAD includes adopted indexes; remove only this study's candidates
            # inside the disposable DB to reproduce the correct previous schema.
            with engine.begin() as db:
                for index_name in (
                    "ix_tasks_active_page",
                    "ix_jobs_ready_owner_created",
                    "ix_jobs_retry_owner_at",
                ):
                    db.execute(text("DROP INDEX IF EXISTS " + index_name))
            owners = seed_storage(engine, **fixture)
            with engine.connect() as db:
                version = db.scalar(text("SELECT version()"))
            baseline = {
                "plans": capture_plans(engine, owners[0]),
                "reads": read_study(engine, owners, batched=False, repeats=spec["read_repeats"]),
                "writes": write_study(engine, spec["write_repeats"]),
                "claims": claim_study(engine, owners, claims=2 * len(owners)),
            }
            refill(engine, owners, 1)
            with engine.begin() as db:
                for ddl in INDEX_DDL:
                    db.execute(text(ddl))
                db.execute(text("ANALYZE"))
            optimized = {
                "plans": capture_plans(engine, owners[0]),
                "reads": read_study(engine, owners, batched=True, repeats=spec["read_repeats"]),
                "writes": write_study(engine, spec["write_repeats"]),
                "claims": claim_study(engine, owners, claims=2 * len(owners)),
            }
            report["workloads"][name] = {
                "postgres": version,
                "fixture": fixture,
                "baseline": baseline,
                "optimized": optimized,
            }
            engine.dispose()
            print(
                json.dumps(
                    {
                        "workload": name,
                        "baseline_read_p95": baseline["reads"]["latency_ms"]["p95"],
                        "optimized_read_p95": optimized["reads"]["latency_ms"]["p95"],
                        "claim_errors": len(baseline["claims"]["errors"])
                        + len(optimized["claims"]["errors"]),
                    }
                ),
                flush=True,
            )
        report["workloads"][name]["isolated_database_dropped"] = True
        output = Path(spec["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        report["client_cpu_ms"] = (process_time() - cpu_start) * 1000
        report["elapsed_ms"] = (perf_counter() - study_start) * 1000
        report["client_peak_rss_bytes"] = rss_bytes()
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
