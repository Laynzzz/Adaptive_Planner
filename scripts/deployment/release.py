"""Explicit AWS release; called only by the protected, manually dispatched workflow."""

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


def aws_cli(arguments, payload=None):
    with tempfile.TemporaryDirectory(prefix="planner-release-") as temporary:
        command = ["aws", *arguments, "--output", "json"]
        if payload is not None:
            path = Path(temporary) / "request.json"
            path.write_text(json.dumps(payload))
            command += ["--cli-input-json", "file://" + str(path)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else {}


def task_revision(aws, arn, image):
    current = aws(["ecs", "describe-task-definition", "--task-definition", arn])["taskDefinition"]
    allowed = {
        "family",
        "taskRoleArn",
        "executionRoleArn",
        "networkMode",
        "containerDefinitions",
        "volumes",
        "placementConstraints",
        "requiresCompatibilities",
        "cpu",
        "memory",
        "pidMode",
        "ipcMode",
        "proxyConfiguration",
        "inferenceAccelerators",
        "ephemeralStorage",
        "runtimePlatform",
    }
    definition = {k: v for k, v in current.items() if k in allowed}
    for container in definition["containerDefinitions"]:
        if container["name"] in ("planner", "migration", "scratch-init"):
            container["image"] = image
    return aws(["ecs", "register-task-definition"], definition)["taskDefinition"][
        "taskDefinitionArn"
    ]


def release(config, image, *, aws=aws_cli, smoke):
    if not re.search(r"@sha256:[a-f0-9]{64}$", image):
        raise ValueError("Release image must be pinned by digest")
    cluster = config["cluster"]
    names = list(config["services"].values())
    previous = aws(["ecs", "describe-services", "--cluster", cluster, "--services", *names])[
        "services"
    ]
    if len(previous) != len(names):
        raise ValueError("Incomplete current service inventory")
    migration = task_revision(aws, config["migration_task"], image)
    started = aws(
        ["ecs", "run-task"],
        {
            "cluster": cluster,
            "taskDefinition": migration,
            "launchType": "FARGATE",
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": config["subnets"],
                    "securityGroups": [config["task_security_group"]],
                    "assignPublicIp": "ENABLED",
                }
            },
        },
    )
    if started.get("failures") or len(started.get("tasks", [])) != 1:
        raise RuntimeError("Migration task did not start")
    task = started["tasks"][0]["taskArn"]
    aws(["ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", task])
    result = aws(["ecs", "describe-tasks", "--cluster", cluster, "--tasks", task])["tasks"][0]
    containers = result.get("containers", [])
    if not containers or any(c.get("exitCode") != 0 for c in containers):
        raise RuntimeError("Migration failed; no service has been updated")
    updated = []
    try:
        for service in previous:
            revision = task_revision(aws, service["taskDefinition"], image)
            # Record before mutation so a timed-out UpdateService is also rolled back.
            updated.append(service)
            aws(
                [
                    "ecs",
                    "update-service",
                    "--cluster",
                    cluster,
                    "--service",
                    service["serviceName"],
                    "--task-definition",
                    revision,
                    "--desired-count",
                    "1",
                ]
            )
        aws(["ecs", "wait", "services-stable", "--cluster", cluster, "--services", *names])
        # A circuit-breaker rollback can also become stable: verify actual target revisions.
        current = aws(["ecs", "describe-services", "--cluster", cluster, "--services", *names])[
            "services"
        ]
        for service in current:
            definition = aws(
                ["ecs", "describe-task-definition", "--task-definition", service["taskDefinition"]]
            )["taskDefinition"]
            selected = next(c for c in definition["containerDefinitions"] if c["name"] == "planner")
            if selected["image"] != image:
                raise RuntimeError("Deployment rolled back before smoke")
        smoke(config["application_url"])
        return {"state": "DEPLOYED", "image": image, "migration_task": task}
    except Exception:
        failures = []
        for service in updated:
            try:
                aws(
                    [
                        "ecs",
                        "update-service",
                        "--cluster",
                        cluster,
                        "--service",
                        service["serviceName"],
                        "--task-definition",
                        service["taskDefinition"],
                        "--desired-count",
                        str(service["desiredCount"]),
                    ]
                )
            except Exception:
                failures.append(service["serviceName"])
        if failures:
            raise RuntimeError("Rollback failed for service names: " + ",".join(failures)) from None
        aws(["ecs", "wait", "services-stable", "--cluster", cluster, "--services", *names])
        if any(service["desiredCount"] > 0 for service in previous):
            try:
                smoke(config["application_url"])
            except Exception:
                raise RuntimeError(
                    "Rollback selected previous definitions, but workflow verification failed"
                ) from None
            raise RuntimeError(
                "Release failed; previous task definitions restored and workflow verified"
            ) from None
        raise RuntimeError("First release failed; initial zero task counts restored") from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--inject-failed-smoke", action="store_true")
    args = parser.parse_args()
    config = {k: v["value"] for k, v in json.loads(args.outputs.read_text()).items()}

    injected = False

    def smoke(origin):
        nonlocal injected
        with urlopen(origin + "/health/ready", timeout=5) as response:
            if response.status != 200:
                raise RuntimeError("Readiness failed")
        if args.inject_failed_smoke and not injected:
            injected = True
            raise RuntimeError("Controlled failed release rehearsal")
        subprocess.run(
            ["node", "scripts/deployment/cloud_smoke.mjs", origin], check=True, timeout=180
        )

    started = time.monotonic()
    result = release(config, args.image, smoke=smoke)
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
