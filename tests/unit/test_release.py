"""Migration and workflow failure must not leave a partial release selected."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "release", Path(__file__).parents[2] / "scripts/deployment/release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
IMAGE = "example.invalid/planner@sha256:" + "a" * 64
CONFIG = {
    "cluster": "synthetic",
    "services": {"api": "api", "worker": "worker"},
    "migration_task": "migration:1",
    "subnets": ["subnet-synthetic"],
    "task_security_group": "sg-synthetic",
    "application_url": "https://synthetic.invalid",
}


class FakeAWS:
    def __init__(self, migration_exit=0):
        self.migration_exit = migration_exit
        self.updates = []
        self.current = {"api": "api:1", "worker": "worker:1"}
        self.definitions = {
            name + ":1": {
                "family": name,
                "containerDefinitions": [
                    {
                        "name": "migration" if name == "migration" else "planner",
                        "image": "old-image",
                    }
                ],
            }
            for name in ("api", "worker", "migration")
        }

    def __call__(self, args, payload=None):
        op = args[1]
        if op == "describe-services":
            return {
                "services": [
                    {"serviceName": name, "taskDefinition": arn, "desiredCount": 1}
                    for name, arn in self.current.items()
                ]
            }
        if op == "describe-task-definition":
            return {"taskDefinition": self.definitions[args[-1]]}
        if op == "register-task-definition":
            arn = payload["family"] + ":2"
            self.definitions[arn] = payload
            return {"taskDefinition": {"taskDefinitionArn": arn}}
        if op == "run-task":
            return {"tasks": [{"taskArn": "synthetic-task"}]}
        if op == "describe-tasks":
            return {"tasks": [{"containers": [{"exitCode": self.migration_exit}]}]}
        if op == "wait":
            return {}
        if op == "update-service":
            name = args[args.index("--service") + 1]
            arn = args[args.index("--task-definition") + 1]
            self.updates.append((name, arn))
            self.current[name] = arn
            return {}
        raise AssertionError(op)


def test_failed_migration_never_updates_running_services():
    aws = FakeAWS(migration_exit=1)
    with pytest.raises(RuntimeError, match="Migration failed"):
        release.release(CONFIG, IMAGE, aws=aws, smoke=lambda origin: None)
    assert aws.updates == []


def test_failed_workflow_restores_every_previous_task_definition():
    aws = FakeAWS()

    attempts = []

    def fail(origin):
        attempts.append(origin)
        if len(attempts) == 1:
            raise RuntimeError("Synthetic bad workflow")

    with pytest.raises(RuntimeError, match="previous task definitions"):
        release.release(CONFIG, IMAGE, aws=aws, smoke=fail)
    assert aws.current == {"api": "api:1", "worker": "worker:1"}
    assert aws.updates[-2:] == [("api", "api:1"), ("worker", "worker:1")]


def test_rollback_runs_workflow_again_before_claiming_recovery():
    aws = FakeAWS()
    attempts = []

    def smoke(origin):
        attempts.append(origin)
        if len(attempts) == 1:
            raise RuntimeError("New image workflow failed")

    with pytest.raises(RuntimeError):
        release.release(CONFIG, IMAGE, aws=aws, smoke=smoke)
    assert len(attempts) == 2
