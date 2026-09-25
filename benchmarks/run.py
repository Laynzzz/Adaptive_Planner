"""Repeated seeded policy measurements with missing and censored results retained."""

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from benchmarks.generate import generate_scenario
from planner.jobs.subprocesses import run_process


def measure(row, policy, *, budget_ms, wall_ms, seed, frozen_path=None):
    with tempfile.TemporaryDirectory(prefix="planner-benchmark-") as folder:
        request, result = Path(folder) / "request.json", Path(folder) / "result.json"
        start = perf_counter()
        request.write_text(
            json.dumps(
                {
                    "snapshot": row["snapshot"],
                    "policy": policy,
                    "budget_ms": budget_ms,
                    "seed": seed,
                    "tiny_exact": row["family"] == "tiny_exact",
                }
            ),
            encoding="utf-8",
        )
        try:
            completed = run_process(
                [sys.executable, "-m", "benchmarks.child", str(request), str(result)],
                cwd=str(Path(frozen_path).resolve()) if frozen_path else None,
                env={**os.environ, "PYTHONPATH": str(Path(frozen_path).resolve())}
                if frozen_path
                else None,
                timeout_seconds=max(0.001, wall_ms / 1000 - (perf_counter() - start)),
            )
            if completed.reason_code == "WALL_TIMEOUT":
                raise subprocess.TimeoutExpired(policy, wall_ms / 1000)
            output = (
                json.loads(result.read_text(encoding="utf-8"))
                if completed.returncode == 0 and result.exists()
                else {
                    "status": "ERROR",
                    "validated": False,
                    "invalid": False,
                    "quality": None,
                    "candidate": None,
                    "error": "CHILD_CRASH",
                }
            )
        except subprocess.TimeoutExpired:
            output = {
                "status": "UNKNOWN",
                "validated": False,
                "invalid": False,
                "quality": None,
                "candidate": None,
                "error": "WALL_TIMEOUT",
            }
        output.update(
            total_ms=(perf_counter() - start) * 1000,
            policy=policy,
            wall_budget_ms=wall_ms,
            requested_native_budget_ms=budget_ms,
            seed=seed,
        )
        output["startup_and_transport_ms"] = max(
            0, output["total_ms"] - output.get("child_wall_ms", output["total_ms"])
        )
        return output


def scenario_run(index, manifest):
    row = generate_scenario(index, seed=manifest["seed"])
    results = []
    for repeat in range(manifest["repeats"]):
        policies = list(manifest["policies"])
        random.Random(row["seed"] + repeat).shuffle(policies)
        for policy in policies:
            budget = 0 if row["family"] == "zero_budget_control" else manifest["cp_budget_ms"]
            results.append(
                {
                    "repeat": repeat,
                    **measure(
                        row,
                        policy,
                        budget_ms=budget,
                        wall_ms=manifest["policy_wall_ms"],
                        seed=row["seed"] + repeat,
                        frozen_path=manifest.get("frozen_path"),
                    ),
                }
            )
    reference_budget = (
        0 if row["family"] == "zero_budget_control" else manifest["reference_budget_ms"]
    )
    reference = measure(
        row,
        "reference",
        budget_ms=reference_budget,
        wall_ms=manifest["reference_wall_ms"],
        seed=row["seed"],
        frozen_path=manifest.get("frozen_path"),
    )
    return {**row, "results": results, "reference": reference}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    frozen_path = manifest.get("frozen_path")
    if frozen_path and Path(__file__).resolve() != (
        Path(frozen_path) / "benchmarks/run.py"
    ).resolve():
        # Reproduce the controller as well as its children from the pinned release.
        bootstrap = (
            "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); "
            "runpy.run_module('benchmarks.run',run_name='__main__')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", bootstrap, str(Path(frozen_path).resolve()), *sys.argv[1:]],
            check=False,
        )
        raise SystemExit(completed.returncode)
    for path, expected in manifest.get("source_hashes", {}).items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Frozen implementation changed: {path}")
    output = args.output or Path(manifest["output"])
    parts = output.with_suffix(".parts")
    if (output.exists() or parts.exists()) and not args.resume:
        raise SystemExit("Output exists; use --resume with the same frozen manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    parts.mkdir(exist_ok=True)
    manifest_hash = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    checkpoint_manifest = parts / "manifest.json"
    if checkpoint_manifest.exists():
        if (
            json.loads(checkpoint_manifest.read_text(encoding="utf-8"))["manifest_hash"]
            != manifest_hash
        ):
            raise SystemExit("Checkpoint belongs to another manifest")
    else:
        checkpoint_manifest.write_text(
            json.dumps({"manifest_hash": manifest_hash}), encoding="utf-8"
        )
    completed = {int(path.stem) for path in parts.glob("[0-9]*.json")}
    started = perf_counter()
    deadline = started + manifest.get("max_runtime_seconds", 5400)

    def bounded(index):
        if perf_counter() >= deadline:
            return None
        return scenario_run(index, manifest)

    remaining = [index for index in manifest["scenario_ids"] if index not in completed]
    with ThreadPoolExecutor(max_workers=manifest["workers"]) as pool:
        futures = {pool.submit(bounded, index): index for index in remaining}
        for future in as_completed(futures):
            row = future.result()
            if row is None:
                continue
            index = futures[future]
            temporary = parts / f"{index:04d}.tmp"
            temporary.write_text(json.dumps(row, sort_keys=True), encoding="utf-8")
            temporary.replace(parts / f"{index:04d}.json")
            completed.add(index)
            if len(completed) % 100 == 0 or len(completed) == len(manifest["scenario_ids"]):
                print(
                    json.dumps(
                        {
                            "completed": len(completed),
                            "total": len(manifest["scenario_ids"]),
                            "elapsed_seconds": round(perf_counter() - started, 2),
                        }
                    ),
                    flush=True,
                )
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for index in sorted(completed):
            stream.write((parts / f"{index:04d}.json").read_text(encoding="utf-8") + "\n")
    missing = sorted(set(manifest["scenario_ids"]) - completed)
    metadata = {
        "finished_at": datetime.now(UTC).isoformat(),
        "manifest": manifest,
        "manifest_hash": manifest_hash,
        "artifact_hash": hashlib.sha256(output.read_bytes()).hexdigest(),
        "elapsed_seconds_this_run": perf_counter() - started,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "artifact": str(output),
        "completed": len(completed),
        "missing_scenario_ids": missing,
        "state": "COMPLETE" if not missing else "INTERRUPTED_RESUME_REQUIRED",
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({"output": str(output), "elapsed_seconds": metadata["elapsed_seconds_this_run"]})
    )


if __name__ == "__main__":
    main()
