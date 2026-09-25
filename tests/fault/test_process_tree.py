"""Real descendants must not perform work after their owned process scope ends."""

import os
import subprocess
import sys
import time

import pytest

from planner.jobs.subprocesses import run_process


def tree_command(tmp_path, *, parent_exits=False):
    ready, late = tmp_path / "ready", tmp_path / "late"
    child = tmp_path / "descendant.py"
    child.write_text(
        "import pathlib,sys,time\n"
        "pathlib.Path(sys.argv[1]).write_text('ready')\n"
        "time.sleep(1.0)\n"
        "pathlib.Path(sys.argv[2]).write_text('survived')\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess,sys,time,pathlib\n"
        "subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2],sys.argv[3]])\n"
        "while not pathlib.Path(sys.argv[2]).exists(): time.sleep(.01)\n"
        + ("" if parent_exits else "time.sleep(2)\n"),
        encoding="utf-8",
    )
    return [sys.executable, str(parent), str(child), str(ready), str(late)], ready, late


@pytest.mark.parametrize("termination", ["timeout", "cancel", "parent_exit", "callback_error"])
def test_descendant_cannot_write_after_process_scope_ends(tmp_path, termination):
    command, ready, late = tree_command(tmp_path, parent_exits=termination == "parent_exit")

    def cancelled():
        if termination == "callback_error" and ready.exists():
            raise RuntimeError("state check failed")
        return termination == "cancel" and ready.exists()

    if termination == "callback_error":
        with pytest.raises(RuntimeError, match="state check failed"):
            run_process(command, timeout_seconds=3, is_cancelled=cancelled)
    else:
        result = run_process(
            command,
            timeout_seconds=0.6 if termination == "timeout" else 3,
            is_cancelled=cancelled,
        )
        assert (
            result.reason_code
            == {"timeout": "WALL_TIMEOUT", "cancel": "SUPERSEDED", "parent_exit": None}[termination]
        )
    assert ready.exists(), "The actual descendant must have started before testing cleanup"
    time.sleep(1.2)
    assert not late.exists(), "A descendant wrote after the process scope ended"


def test_process_scope_passes_environment_and_working_directory(tmp_path):
    result = run_process(
        [
            sys.executable,
            "-c",
            "import os,pathlib; pathlib.Path('result').write_text(os.environ['PLANNER_TREE_TEST'])",
        ],
        env={**os.environ, "PLANNER_TREE_TEST": "isolated"},
        cwd=tmp_path,
    )
    assert result.returncode == 0 and result.reason_code is None
    assert (tmp_path / "result").read_text() == "isolated"


def test_failed_launch_does_not_hide_the_error(tmp_path):
    with pytest.raises(OSError):
        run_process([str(tmp_path / "nonexistent-executable")], timeout_seconds=1)


def test_deadline_stops_descendants_after_parent_exit_during_blocked_callback(tmp_path):
    command, ready, late = tree_command(tmp_path, parent_exits=True)

    def slow_check():
        time.sleep(1.7)
        return False

    result = run_process(command, timeout_seconds=0.6, is_cancelled=slow_check)
    assert ready.exists()
    assert not late.exists(), "Watchdog must own descendants even after the immediate parent exits"
    assert result.reason_code == "WALL_TIMEOUT"


@pytest.mark.skipif(os.name != "nt", reason="Windows job kernel owns crash cleanup")
def test_windows_job_closes_when_supervisor_exits_abruptly(tmp_path):
    command, ready, late = tree_command(tmp_path)
    supervisor = tmp_path / "supervisor.py"
    supervisor.write_text(
        "import json,os,pathlib,sys,time\n"
        "from planner.jobs.process_tree import spawn_process_tree\n"
        "process = spawn_process_tree(json.loads(sys.argv[1]))\n"
        "while not pathlib.Path(sys.argv[2]).exists(): time.sleep(.01)\n"
        "os._exit(0)\n",
        encoding="utf-8",
    )
    import json

    subprocess.run(
        [sys.executable, str(supervisor), json.dumps(command), str(ready)], timeout=3, check=True
    )
    assert ready.exists()
    time.sleep(1.2)
    assert not late.exists(), "A hard supervisor exit must close its noninherited job handle"


@pytest.mark.skipif(os.name != "nt", reason="Windows atomic job assignment API")
def test_windows_containment_failure_never_launches_the_command(tmp_path, monkeypatch):
    from planner.jobs import windows_process

    marker = tmp_path / "must-not-launch"

    def reject_attribute(*args):
        raise OSError("job containment unavailable")

    monkeypatch.setattr(windows_process, "UpdateAttributes", reject_attribute)
    with pytest.raises(OSError, match="job containment unavailable"):
        run_process(
            [
                sys.executable,
                "-c",
                "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()",
                str(marker),
            ]
        )
    time.sleep(0.1)
    assert not marker.exists()
