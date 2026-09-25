"""Bounded synthetic faults against a disposable database and expendable worker."""

# ruff: noqa: F811 -- imported fixtures are injected by pytest.
import json
import os
import subprocess
import sys
import threading
import time
from datetime import timedelta

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from planner.ai.provider import ProviderError
from planner.ai.worker import run_once
from planner.db.job_models import Job
from planner.jobs.coalescing import enqueue
from planner.jobs.dispatcher import claim_next
from planner.jobs.leases import reconcile_expired
from planner.jobs.worker import work_claim
from planner.observability.database import instrument_engine
from planner.observability.runtime import span, use
from planner.observability.state import register_state_metrics
from tests.integration.conftest import api_a, app  # noqa: F401
from tests.integration.test_jobs import NOW, job_engine, seed_owner  # noqa: F401
from tests.integration.test_observability import recorder  # noqa: F401


def test_database_interruption_is_redacted_and_recovers(
    api_a, app, recorder, migrated_database_url
):
    telemetry, exporter, _ = recorder
    target = make_url(migrated_database_url)
    assert target.database.startswith("planner_test_")
    admin_url = target.set(database="postgres", drivername="postgresql")
    app.state.engine.dispose()
    started = time.perf_counter()
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as admin:
        admin.execute(
            sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(
                sql.Identifier(target.database)
            )
        )
        try:
            failed = api_a.get("/api/v1/tasks?code=PRIVATE_OAUTH&state=PRIVATE_STATE")
            assert failed.status_code == 503, failed.text
            assert failed.json()["code"] == "DEPENDENCY_UNAVAILABLE"
            assert failed.headers["cache-control"] == "no-store"
        finally:
            admin.execute(
                sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(
                    sql.Identifier(target.database)
                )
            )
    recovered = api_a.get("/api/v1/tasks")
    assert recovered.status_code == 200
    spans = exporter.get_finished_spans()
    requests = [s for s in spans if s.name == "api.request"]
    assert [s.attributes["http.status_code"] for s in requests[-2:]] == [503, 200]
    assert "PRIVATE_" not in json.dumps([s.to_json() for s in spans])
    print(
        json.dumps(
            {
                "fault": "database_connections_disabled",
                "detected_and_recovered_seconds": round(time.perf_counter() - started, 3),
                "states": [503, 200],
            }
        )
    )


def test_throttled_provider_fails_durably_and_next_request_recovers(api_a, app, recorder):
    telemetry, exporter, _ = recorder

    class Throttled:
        async def extract(self, context):
            raise ProviderError("PROVIDER_THROTTLED", retryable=True)

    body = {
        "text": "PRIVATE_SYNTHETIC study for 30 minutes",
        "mode": "mock",
        "expected_revision": 0,
    }
    first = api_a.post("/api/v1/interpretations", json=body).json()["id"]
    with use(telemetry):
        assert run_once(app.state.engine, provider=Throttled())
    failed = api_a.get("/api/v1/interpretations/" + first).json()
    assert (failed["state"], failed["error_code"]) == ("FAILED", "PROVIDER_THROTTLED")
    second = api_a.post("/api/v1/interpretations", json=body).json()["id"]
    with use(telemetry):
        assert run_once(app.state.engine)
    assert api_a.get("/api/v1/interpretations/" + second).json()["state"] == "READY"
    spans = exporter.get_finished_spans()
    errors = [
        s for s in spans if s.name == "provider.call" and s.status.status_code.name == "ERROR"
    ]
    assert len(errors) == 1 and errors[0].attributes["error.type"] == "ProviderError"
    assert "PRIVATE_SYNTHETIC" not in json.dumps([s.to_json() for s in spans])
    print(
        json.dumps(
            {
                "fault": "synthetic_provider_throttle",
                "states": ["FAILED", "READY"],
                "automatic_retry": False,
            }
        )
    )


def test_killed_claim_is_detected_then_recovered_with_trace_link(
    job_engine, app, recorder, tmp_path
):
    telemetry, exporter, reader = recorder
    instrument_engine(job_engine)
    owner = seed_owner(job_engine)
    with use(telemetry), span("api.request"):
        job_id = enqueue(job_engine, owner, now=NOW, explicit=True)
    marker = tmp_path / "claimed.txt"
    script = """import os,time
from pathlib import Path
from datetime import datetime
from planner.db.session import create_db_engine
from planner.settings import Settings
from planner.jobs.dispatcher import claim_next
engine=create_db_engine(Settings())
claim=claim_next(engine,now=datetime.fromisoformat(os.environ['SYNTHETIC_NOW']))
assert claim is not None
Path(os.environ['SYNTHETIC_MARKER']).write_text(str(claim.fencing_token))
time.sleep(60)
"""
    env = {
        **os.environ,
        "PLANNER_DATABASE_URL": job_engine.url.render_as_string(hide_password=False),
        "SYNTHETIC_NOW": NOW.isoformat(),
        "SYNTHETIC_MARKER": str(marker),
    }
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    started = time.perf_counter()
    try:
        while not marker.exists() and time.perf_counter() - started < 10:
            assert process.poll() is None
            time.sleep(0.05)
        assert marker.exists()
        first_token = int(marker.read_text())
    finally:
        process.kill()
        process.wait(timeout=3)
    with Session(job_engine) as db:
        assert db.get(Job, job_id).state == "RUNNING"
    # Deterministic lease clock advances 31 seconds; no real 31-second sleep.
    assert reconcile_expired(job_engine, now=NOW + timedelta(seconds=31)) == 1
    health = register_state_metrics(telemetry, job_engine)
    assert health()["planner.jobs.lease_lost"][0].value == 1
    claim = claim_next(job_engine, now=NOW + timedelta(seconds=32))
    assert claim.fencing_token > first_token
    with use(telemetry):
        result = work_claim(
            job_engine, claim, threading.Event(), clock=lambda: NOW + timedelta(seconds=33)
        )
    assert result.state == "SUCCEEDED"
    spans = exporter.get_finished_spans()
    request = next(s for s in spans if s.name == "api.request")
    worker = next(s for s in spans if s.name == "job.solve")
    assert worker.context.trace_id == request.context.trace_id
    assert reader.get_metrics_data() is not None
    print(
        json.dumps(
            {
                "fault": "killed_worker_process",
                "states": ["RUNNING", "QUEUED", "SUCCEEDED"],
                "lease_clock_advance_seconds": 31,
                "wall_seconds": round(time.perf_counter() - started, 3),
            }
        )
    )
