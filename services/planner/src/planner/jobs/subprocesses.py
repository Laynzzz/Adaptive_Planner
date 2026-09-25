"""Bounded child processes; the parent owns cancellation and heartbeat timing."""

import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from planner.domain.contracts import Candidate, InputSnapshot
from planner.solver.greedy import greedy_schedule
from planner.solver.validator import validate_candidate


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    reason_code: str | None
    elapsed_seconds: float


def run_process(
    command: list[str],
    *,
    timeout_seconds: float = 5,
    is_cancelled: Callable[[], bool] | None = None,
    on_heartbeat: Callable[[], bool] | None = None,
) -> ProcessResult:
    start = time.monotonic()
    next_heartbeat = start + 5
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    deadline_expired = threading.Event()

    def enforce_deadline():
        if process.poll() is None:
            deadline_expired.set()
            try:
                process.kill()
            except ProcessLookupError:
                pass

    timer = threading.Timer(max(0, timeout_seconds - (time.monotonic() - start)), enforce_deadline)
    timer.daemon = True
    timer.start()
    reason = None
    try:
        while process.poll() is None:
            now = time.monotonic()
            if is_cancelled is not None and is_cancelled():
                reason = "SUPERSEDED"
                break
            if now - start >= timeout_seconds:
                reason = "WALL_TIMEOUT"
                break
            if now >= next_heartbeat and on_heartbeat is not None:
                if not on_heartbeat():
                    reason = "LEASE_LOST"
                    break
                next_heartbeat = now + 5
            try:
                process.wait(timeout=min(0.1, max(0.001, timeout_seconds - (now - start))))
            except subprocess.TimeoutExpired:
                pass
    finally:
        timer.cancel()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.3)
    if deadline_expired.is_set():
        reason = "WALL_TIMEOUT"
    return ProcessResult(process.returncode, reason, time.monotonic() - start)


@dataclass(frozen=True)
class SolveResult:
    candidate: Candidate | None
    reason_code: str | None


def run_solver(
    snapshot: InputSnapshot, *, timeout_seconds=5, is_cancelled=None, on_heartbeat=None
) -> SolveResult:
    with tempfile.TemporaryDirectory(prefix="planner-solve-") as directory:
        request = Path(directory) / "snapshot.json"
        result = Path(directory) / "candidate.json"
        request.write_text(snapshot.model_dump_json(exclude_computed_fields=True), encoding="utf-8")
        outcome = run_process(
            [sys.executable, "-m", "planner.jobs.solve_child", str(request), str(result)],
            timeout_seconds=timeout_seconds,
            is_cancelled=is_cancelled,
            on_heartbeat=on_heartbeat,
        )
        if outcome.reason_code == "WALL_TIMEOUT":
            fallback = greedy_schedule(snapshot)
            if fallback.status in ("FEASIBLE", "OPTIMAL") and not validate_candidate(
                snapshot, fallback
            ):
                metadata = fallback.solver_metadata.model_copy(
                    update={"reason_code": "WALL_TIMEOUT"}
                )
                return SolveResult(
                    fallback.model_copy(
                        update={"source_policy": "GREEDY_FALLBACK", "solver_metadata": metadata}
                    ),
                    None,
                )
        if outcome.reason_code:
            return SolveResult(None, outcome.reason_code)
        if outcome.returncode != 0 or not result.exists():
            return SolveResult(None, "CHILD_CRASH")
        try:
            candidate = Candidate.model_validate_json(result.read_text(encoding="utf-8"))
        except ValueError:
            return SolveResult(None, "INVALID_CHILD_RESULT")
        return SolveResult(candidate, None)
