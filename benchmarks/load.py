"""Fixed-arrival real HTTP/real OIDC load with durable-job latency and backlog sampling."""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from time import perf_counter, sleep
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, insert, select, text
from sqlalchemy.orm import Session

from benchmarks.child import rss_bytes
from benchmarks.sql import distribution
from benchmarks.storage import isolated_database, seed_storage
from planner.db.job_models import Job, SnapshotRecord
from planner.db.models import Availability, DependencyEdge, PendingReplan, Task

BASE = "http://127.0.0.1:38001"


class LoginForm(HTMLParser):
    action = None

    def handle_starttag(self, tag, attributes):
        data = dict(attributes)
        if tag == "form" and data.get("id") == "kc-form-login":
            self.action = data["action"]


def authenticate(username):
    with httpx.Client(base_url=BASE, timeout=10, follow_redirects=False) as api:
        start = api.get("/api/v1/auth/login")
        assert start.status_code == 302
        with httpx.Client(timeout=10, follow_redirects=False) as provider:
            page = provider.get(start.headers["location"])
            assert page.url.host == "127.0.0.1"
            for cookie in provider.cookies.jar:
                cookie.secure = False
            form = LoginForm()
            form.feed(page.text)
            response = provider.post(
                form.action,
                data={
                    "username": username,
                    "password": f"local-{username}-only",
                    "credentialId": "",
                },
            )
            assert response.status_code == 302
            callback = httpx.URL(response.headers["location"])
            signed = api.get(callback.raw_path.decode())
            assert signed.status_code == 302, signed.text
        me = api.get("/api/v1/me")
        assert me.status_code == 200
        return {
            "owner_id": UUID(me.json()["id"]),
            "csrf": me.json()["csrf_token"],
            "cookies": dict(api.cookies),
            "revision": me.json()["revision"],
        }


def seed_http_owner(engine, owner):
    now = datetime.now(UTC)
    tasks = [
        {
            "id": uuid4(),
            "owner_id": owner,
            "title": f"HTTP synthetic task {i}",
            "remaining_minutes": 30 if i < 200 else 0,
            "priority": 3,
            "state": "TODO" if i < 200 else "DONE",
            "details": {},
            "created_at": now + timedelta(microseconds=i)
            if i < 200
            else now - timedelta(days=30, seconds=i),
        }
        for i in range(1000)
    ]
    with engine.begin() as db:
        db.execute(insert(Task), tasks)
        db.execute(
            insert(DependencyEdge),
            [
                {
                    "owner_id": owner,
                    "predecessor_id": tasks[i - 1]["id"],
                    "successor_id": tasks[i]["id"],
                }
                for i in range(1, 1000)
                if i != 200
            ],
        )
        db.execute(
            insert(Availability),
            {
                "owner_id": owner,
                "windows": [
                    {"start": now.isoformat(), "end": (now + timedelta(days=13)).isoformat()}
                ],
            },
        )
        db.execute(
            insert(Job),
            [
                {
                    "id": uuid4(),
                    "owner_id": owner,
                    "kind": "REPLAN",
                    "planning_revision": 0,
                    "calendar_revision": 0,
                    "state": "FAILED",
                    "fencing_token": 1,
                    "attempts": 1,
                    "obsolete": False,
                    "created_at": now - timedelta(days=30, seconds=i),
                    "finished_at": now - timedelta(days=29, seconds=i),
                    "reason_code": "SYNTHETIC_HTTP_ARCHIVE",
                }
                for i in range(1000)
            ],
        )


def sample_queue(engine, owners, started):
    with Session(engine) as db:
        states = dict(
            db.execute(
                select(Job.state, func.count()).where(Job.owner_id.in_(owners)).group_by(Job.state)
            ).all()
        )
        oldest = db.scalar(
            select(func.min(PendingReplan.enqueued_at)).where(PendingReplan.owner_id.in_(owners))
        )
        now = datetime.now(UTC)
        return {
            "elapsed_seconds": perf_counter() - started,
            "queued": states.get("QUEUED", 0) + states.get("RETRY_WAIT", 0),
            "running": states.get("RUNNING", 0),
            "oldest_pending_seconds": max(0, (now - oldest).total_seconds()) if oldest else 0,
        }


async def arrivals(users, duration, rate, engine):
    started = perf_counter()
    records = []
    dropped = 0
    samples = []
    pending = set()
    clients = [
        httpx.AsyncClient(
            base_url=BASE,
            cookies=user["cookies"],
            timeout=10,
            headers={"X-CSRF-Token": user["csrf"]},
        )
        for user in users
    ]

    async def one(index):
        owner = (index // 10) % len(users) if index % 10 == 9 else index % len(users)
        operation = (
            "tasks"
            if index % 10 < 6
            else ("me" if index % 10 < 8 else ("availability" if index % 10 == 8 else "generate"))
        )
        start = perf_counter()
        status = None
        error = None
        job_id = None
        try:
            if operation == "generate":
                response = await clients[owner].post(
                    "/api/v1/replans",
                    json={"expected_revision": users[owner]["revision"]},
                    headers={"Idempotency-Key": str(uuid4())},
                )
                if response.status_code == 202:
                    job_id = response.json()["job_id"]
            else:
                path = {
                    "tasks": "/api/v1/tasks?state=TODO&limit=50",
                    "me": "/api/v1/me",
                    "availability": "/api/v1/availability",
                }[operation]
                response = await clients[owner].get(path)
            status = response.status_code
        except httpx.HTTPError as failure:
            error = type(failure).__name__
        records.append(
            {
                "index": index,
                "operation": operation,
                "owner_index": owner,
                "status": status,
                "error": error,
                "latency_ms": (perf_counter() - start) * 1000,
                "job_id": job_id,
                "started_elapsed_seconds": start - started,
            }
        )

    try:
        for index in range(int(duration * rate)):
            target = started + index / rate
            await asyncio.sleep(max(0, target - perf_counter()))
            if perf_counter() - target > max(1, 2 / rate) or len(pending) >= 8:
                dropped += 1
                continue
            task = asyncio.create_task(one(index))
            pending.add(task)
            task.add_done_callback(pending.discard)
            if index % max(1, int(rate * 5)) == 0:
                samples.append(
                    await asyncio.to_thread(
                        sample_queue, engine, [u["owner_id"] for u in users], started
                    )
                )
        if pending:
            await asyncio.gather(*pending)
    finally:
        for client in clients:
            await client.aclose()
    samples.append(sample_queue(engine, [u["owner_id"] for u in users], started))
    return {
        "records": records,
        "dropped_iterations": dropped,
        "queue_samples": samples,
        "elapsed_seconds": perf_counter() - started,
    }


def job_timings(engine, ids):
    values = []
    with Session(engine) as db:
        for job in db.scalars(select(Job).where(Job.id.in_([UUID(id) for id in ids]))):
            snapshot = db.get(SnapshotRecord, job.snapshot_id) if job.snapshot_id else None
            metadata = (job.result or {}).get("solver_metadata", {})
            values.append(
                {
                    "state": job.state,
                    "reason_code": job.reason_code,
                    "queue_ms": max(
                        0, (snapshot.created_at - job.created_at).total_seconds() * 1000
                    )
                    if snapshot
                    else None,
                    "ready_to_inspect_ms": (job.finished_at - job.created_at).total_seconds() * 1000
                    if job.finished_at
                    else None,
                    "solver_reported_ms": metadata.get("runtime_ms"),
                    "solver_status": (job.result or {}).get("status"),
                }
            )
    return values


def summary(result):
    records = result["records"]
    samples = result["queue_samples"]
    codes = Counter(str(r["status"]) if r["status"] is not None else r["error"] for r in records)
    slope = (
        (samples[-1]["queued"] + samples[-1]["running"])
        - (samples[0]["queued"] + samples[0]["running"])
    ) / max(1, result["elapsed_seconds"])
    return {
        "requests": len(records),
        "status_counts": dict(codes),
        "dropped_iterations": result["dropped_iterations"],
        "all_http_ms": distribution([r["latency_ms"] for r in records]),
        "by_operation_ms": {
            name: distribution([r["latency_ms"] for r in records if r["operation"] == name])
            for name in ("tasks", "me", "availability", "generate")
        },
        "backlog_slope_jobs_per_second": slope,
        "oldest_pending_max_seconds": max(s["oldest_pending_seconds"] for s in samples),
        "queue_samples": samples,
        "job_outcomes": dict(Counter(x["state"] for x in result.get("jobs", []))),
        "queue_ms": distribution(
            [x["queue_ms"] for x in result.get("jobs", []) if x["queue_ms"] is not None]
        ),
        "ready_to_inspect_ms": distribution(
            [
                x["ready_to_inspect_ms"]
                for x in result.get("jobs", [])
                if x["ready_to_inspect_ms"] is not None
            ]
        ),
        "solver_reported_ms": distribution(
            [
                x["solver_reported_ms"]
                for x in result.get("jobs", [])
                if x["solver_reported_ms"] is not None
            ]
        ),
        "measurement_limits": (
            "Solver metadata runtime includes its internal model/validation; "
            "subprocess policy benchmark provides separate stages. HTTP202 "
            "timing excludes job completion."
        ),
    }


def start_process(command, env, cwd):
    return subprocess.Popen(
        command,
        env=env,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def stop_process(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.manifest.read_text(encoding="utf-8"))
    if Path(spec["output"]).exists():
        raise SystemExit("Output exists; choose a new manifest output to preserve evidence")
    frozen = Path(".runtime/benchmarks/load-v1").resolve()
    if not frozen.exists():
        frozen.mkdir(parents=True)
        shutil.copytree(
            "services/planner/src/planner",
            frozen / "planner",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copytree(
            "benchmarks",
            frozen / "benchmarks",
            ignore=shutil.ignore_patterns("__pycache__", "manifests"),
        )
    report = {
        "manifest": spec,
        "manifest_hash": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "frozen_source_hash": hashlib.sha256(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(frozen.rglob("*.py"))
            ).encode()
        ).hexdigest(),
        "shared_host": (
            "Concurrent2slot frozen scheduling benchmark; project verification may also run"
        ),
        "phases": {},
    }
    output = Path(spec["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    for phase in ("baseline", "optimized"):
        server = worker = None
        with isolated_database() as (engine, name):
            seed_storage(
                engine,
                users=100,
                active_tasks=200,
                archived_tasks=800,
                archived_jobs=100000,
                pending_per_owner=0,
            )
            with engine.begin() as db:
                db.execute(text("DELETE FROM pending_replans"))
                if phase == "baseline":
                    for index in (
                        "ix_tasks_active_page",
                        "ix_jobs_ready_owner_created",
                        "ix_jobs_retry_owner_at",
                    ):
                        db.execute(text("DROP INDEX IF EXISTS " + index))
            env = {
                **os.environ,
                "PYTHONPATH": str(frozen),
                "PLANNER_DATABASE_URL": engine.url.render_as_string(hide_password=False),
                "PLANNER_LOAD_PHASE": phase,
            }
            try:
                server = start_process(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "benchmarks.load_server:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "38001",
                        "--no-access-log",
                    ],
                    env,
                    str(frozen),
                )
                for _ in range(100):
                    try:
                        if httpx.get(BASE + "/health/ready", timeout=1).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    sleep(0.1)
                else:
                    raise RuntimeError("Isolated load API failed readiness")
                users = [authenticate("demo-a"), authenticate("demo-b")]
                for user in users:
                    seed_http_owner(engine, user["owner_id"])
                worker = start_process(
                    [sys.executable, "-m", "planner.jobs.worker"], env, str(frozen)
                )
                if phase == "baseline":
                    pilot = asyncio.run(
                        arrivals(users, spec["pilot_seconds"], spec["pilot_rate"], engine)
                    )
                    pilot["jobs"] = job_timings(
                        engine, {r["job_id"] for r in pilot["records"] if r["job_id"]}
                    )
                    report["pilot"] = summary(pilot)
                    if any(
                        int(code) >= 500
                        for code in report["pilot"]["status_counts"]
                        if code.isdigit()
                    ):
                        raise RuntimeError("Pilot server errors; full load not launched")
                    chosen = spec["pilot_rate"] / 2
                    report["frozen_arrival_rate"] = chosen
                    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                rate = report["frozen_arrival_rate"]
                asyncio.run(arrivals(users, spec["warmup_seconds"], rate, engine))
                result = asyncio.run(arrivals(users, spec["duration_seconds"], rate, engine))
                sleep(5)
                result["jobs"] = job_timings(
                    engine, {r["job_id"] for r in result["records"] if r["job_id"]}
                )
                report["phases"][phase] = summary(result)
                report["phases"][phase]["request_records"] = result["records"]
                report["phases"][phase]["jobs"] = result["jobs"]
                report["client_peak_rss_bytes"] = rss_bytes()
                output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(
                    json.dumps(
                        {
                            "phase": phase,
                            "requests": len(result["records"]),
                            "dropped": result["dropped_iterations"],
                            "status": report["phases"][phase]["status_counts"],
                        }
                    ),
                    flush=True,
                )
            finally:
                stop_process(worker)
                stop_process(server)
                engine.dispose()
        report["phases"].get(phase, {})["isolated_database_dropped"] = True
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
