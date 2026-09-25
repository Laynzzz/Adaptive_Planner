"""Disposable local old-image, additive-migration and backup/restore rehearsal."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from uuid import uuid4

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import make_url

from planner.db.session import migration_config

ROOT = Path(__file__).resolve().parents[2]
admin_url = make_url(
    os.environ.get(
        "PLANNER_TEST_ADMIN_URL",
        "postgresql+psycopg://planner:local-planner-only@127.0.0.1:25432/postgres",
    )
)
source = "planner_rehearsal_" + uuid4().hex
restored = "planner_restore_" + uuid4().hex
owner = str(uuid4())
task = str(uuid4())
postgres_container = os.environ.get("PLANNER_POSTGRES_CONTAINER", "adaptive-planner-postgres-1")
new_image = os.environ.get("PLANNER_REHEARSAL_IMAGE", "adaptive-planner:local-r4")
report = {"database_scope": "two newly created disposable databases", "steps": [], "images": {}}
started = time.perf_counter()


def db_url(name, container=False):
    return admin_url.set(
        database=name, host="host.docker.internal" if container else admin_url.host
    )


def record(step, **details):
    report["steps"].append(
        {"step": step, "elapsed_seconds": round(time.perf_counter() - started, 3), **details}
    )


def image_run(image, name, arguments, expected=0):
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,size=128m",
            "--env",
            "PLANNER_DATABASE_URL",
            image,
            *arguments,
        ],
        env={
            **os.environ,
            "PLANNER_DATABASE_URL": db_url(name, True).render_as_string(hide_password=False),
        },
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == expected, {
        "image": image,
        "exit": result.returncode,
        "expected": expected,
        "stderr": result.stderr[-800:],
    }
    return result.stdout


def image_http_smoke(image, name):
    cid = subprocess.check_output(
        [
            "docker",
            "run",
            "-d",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,size=128m",
            "-p",
            "127.0.0.1::8000",
            "--env",
            "PLANNER_DATABASE_URL",
            image,
        ],
        env={
            **os.environ,
            "PLANNER_DATABASE_URL": db_url(name, True).render_as_string(hide_password=False),
        },
        text=True,
    ).strip()
    try:
        info = json.loads(subprocess.check_output(["docker", "inspect", cid], text=True))[0]
        port = info["NetworkSettings"]["Ports"]["8000/tcp"][0]["HostPort"]
        base = "http://127.0.0.1:" + port
        for _ in range(80):
            try:
                with urlopen(base + "/health/ready", timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, HTTPError):
                time.sleep(0.1)
        else:
            raise AssertionError("Container readiness did not become200")
        with urlopen(base + "/", timeout=3) as response:
            assert response.status == 200 and b"<html" in response.read().lower()
        try:
            urlopen(base + "/api/v1/tasks", timeout=3)
        except HTTPError as error:
            assert error.code == 401
        else:
            raise AssertionError("Unauthenticated task list must remain protected")
        assert info["Config"]["User"] == "10001:10001"
        assert info["HostConfig"]["ReadonlyRootfs"]
    finally:
        subprocess.run(["docker", "rm", "-f", cid], check=True, stdout=subprocess.DEVNULL)


def checksum(name):
    result = {}
    with psycopg.connect(
        db_url(name).set(drivername="postgresql").render_as_string(hide_password=False)
    ) as db:
        tables = [
            r[0]
            for r in db.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
        ]
        for table in tables:
            rows = [
                r[0]
                for r in db.execute(
                    sql.SQL("SELECT to_jsonb(t) FROM {} t").format(sql.Identifier(table))
                )
            ]
            canonical = "\n".join(
                sorted(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows)
            )
            result[table] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            }
    return result


admin = psycopg.connect(
    admin_url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
)
try:
    for name in (source, restored):
        assert name.startswith(("planner_rehearsal_", "planner_restore_"))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    config = migration_config()
    config.attributes["database_url"] = db_url(source).render_as_string(hide_password=False)
    command.upgrade(config, "0014_sql_indexes")
    with psycopg.connect(
        db_url(source).set(drivername="postgresql").render_as_string(hide_password=False)
    ) as db:
        db.execute(
            "INSERT INTO identities(id,issuer,subject,name,timezone) VALUES(%s,'https://synthetic.invalid','release-rehearsal','Synthetic','UTC')",
            (owner,),
        )
        db.execute("INSERT INTO user_planning_state(owner_id,revision) VALUES(%s,0)", (owner,))
        db.execute(
            "INSERT INTO tasks(id,owner_id,title,remaining_minutes,priority,state,details) "
            "VALUES(%s,%s,'Synthetic draft',60,3,'TODO','{}')",
            (task, owner),
        )
        db.execute(
            "INSERT INTO availability_rules(owner_id,windows) VALUES(%s,%s::jsonb)",
            (owner, json.dumps([{"start": "2026-09-25T09:00:00Z", "end": "2026-09-25T17:00:00Z"}])),
        )
    for image in ("adaptive-planner:prior-unmodified", "adaptive-planner:prior-bridge", new_image):
        report["images"][image] = subprocess.check_output(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
        ).strip()
    assert (
        image_run(
            "adaptive-planner:prior-unmodified",
            source,
            ["python", "-m", "planner.cli", "check-ready"],
        ).strip()
        == "ready"
    )
    record("unmodified_prior_on_prior_schema", ready=True)
    command.upgrade(config, "head")
    assert (
        image_run(
            "adaptive-planner:prior-unmodified",
            source,
            ["python", "-m", "planner.cli", "check-ready"],
            expected=1,
        ).strip()
        == "not_ready"
    )
    record(
        "unmodified_prior_after_additive_migration",
        ready=False,
        limitation="Strict original head equality rejects additive schema",
    )
    assert (
        image_run(
            "adaptive-planner:prior-bridge", source, ["python", "-m", "planner.cli", "check-ready"]
        ).strip()
        == "ready"
    )
    smoke = f"""
from datetime import UTC,datetime
from uuid import UUID
from sqlalchemy.orm import Session
from planner.db.session import create_db_engine
from planner.settings import Settings
from planner.db.models import Task
from planner.domain.commands import execute_command
from planner.jobs.coalescing import enqueue
from planner.jobs.dispatcher import claim_next
from planner.jobs.handlers import finalize
from planner.solver.greedy import greedy_schedule
from planner.domain.plans import activate_proposal
now=datetime(2026,9,25,9,tzinfo=UTC)
engine=create_db_engine(Settings())
owner=UUID('{owner}')
def change(db):
 db.get(Task,UUID('{task}')).remaining_minutes=45
 return {{'updated':True}}
body={{'expected_revision':0}}
first=execute_command(engine,owner,'REHEARSAL_UPDATE','replay-key',body,lambda:now,change)
assert first[0]['revision']==1
assert execute_command(engine,owner,'REHEARSAL_UPDATE','replay-key',body,lambda:now,change)==first
enqueue(engine,owner,now=now,explicit=True)
claim=claim_next(engine,now=now)
result=finalize(engine,claim,greedy_schedule(claim.snapshot),now=now)
assert result.state=='SUCCEEDED'
activation=activate_proposal(engine,owner,result.proposal_id,expected_revision=1,now=now)
assert activation.code=='ACTIVATED'
engine.dispose()
print('old-business-command-idempotency-solve-activation-ok')
"""
    assert "activation-ok" in image_run(
        "adaptive-planner:prior-bridge", source, ["python", "-c", smoke]
    )
    image_http_smoke("adaptive-planner:prior-bridge", source)
    record(
        "bridge_prior_after_migration",
        ready=True,
        old_command_idempotency_solve_activation=True,
        single_origin_html=True,
        unauthorized_api_status=401,
        nonroot_readonly=True,
    )
    before = checksum(source)
    backup = ROOT / ".runtime" / ("backup-" + uuid4().hex + ".dump")
    docker_env = {**os.environ, "PGPASSWORD": admin_url.password or ""}
    with backup.open("wb") as output:
        subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                "PGPASSWORD",
                postgres_container,
                "pg_dump",
                "-U",
                admin_url.username,
                "-d",
                source,
                "-Fc",
                "--no-owner",
                "--no-privileges",
            ],
            env=docker_env,
            stdout=output,
            check=True,
        )
    with backup.open("rb") as input:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "-e",
                "PGPASSWORD",
                postgres_container,
                "pg_restore",
                "-U",
                admin_url.username,
                "-d",
                restored,
                "--single-transaction",
                "--no-owner",
                "--no-privileges",
            ],
            env=docker_env,
            stdin=input,
            check=True,
        )
    after = checksum(restored)
    assert before == after
    record(
        "separate_database_backup_restore",
        tables=len(before),
        rows=sum(t["rows"] for t in before.values()),
        logical_record_hashes_equal=True,
        backup_bytes=backup.stat().st_size,
    )
    image_http_smoke(new_image, restored)
    image_http_smoke("adaptive-planner:prior-bridge", restored)
    record(
        "current_and_prior_bridge_against_restored_database",
        ready=True,
        html=True,
        unauthorized_api_status=401,
    )
    report["record_comparison"] = before
    report["status"] = "LOCAL_PASS"
finally:
    for name in (source, restored):
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
    admin.close()
    report["temporary_databases_removed"] = True
    (ROOT / "docs/evidence/raw/task-18-local-rehearsal.json").write_text(
        json.dumps(report, indent=2)
    )
print(json.dumps({k: v for k, v in report.items() if k != "record_comparison"}, indent=2))
