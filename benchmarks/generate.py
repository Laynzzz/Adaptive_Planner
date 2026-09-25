"""Reproducible grouped synthetic workloads with independently validated witnesses."""

import argparse
import hashlib
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from planner.domain.contracts import Block, Candidate, Deadline, Dependency, InputSnapshot, TaskSpec
from planner.solver.objective import score_candidate
from planner.solver.validator import validate_candidate

VERSION = "scheduler-scenarios-v1"
CLOCK = datetime(2026, 9, 25, tzinfo=UTC)


def partition(index):
    if not 0 <= index < 1000:
        raise ValueError("Base scenario index must be within the frozen 1000-group release")
    return "train" if index < 600 else ("validation" if index < 800 else "test")


def digest_snapshot(snapshot):
    payload = snapshot.model_dump(mode="json", exclude={"id", "snapshot_hash"})
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return snapshot.model_copy(update={"id": UUID(hex=digest[:32]), "snapshot_hash": digest})


def generate_scenario(index, *, seed=20260925):
    split = partition(index)
    rng = random.Random(seed + index * 104729)
    tiny = index % 10 == 0
    count = 3 if tiny else (20, 50, 100, 200)[index % 4]
    horizon = 8 if tiny else 1344
    owner = uuid5(NAMESPACE_URL, f"{VERSION}/{seed}/{index}")
    mode = (
        "infeasible"
        if index % 25 == 24
        else ("zero_budget_control" if index % 25 == 23 else "feasible")
    )
    if tiny:
        mode = "tiny_exact"
    # Dense fragmentation plus high dependency rate is reserved for the last 100 test groups.
    robustness = index >= 900
    fragmented = (index % 3 == 0 or robustness) and not tiny
    gap = 1 if fragmented else 0
    locked_fraction = 0 if tiny else (0.15 if robustness else (index % 3) * 0.05)
    dependency_rate = 0.6 if robustness else (index % 4) * 0.1
    slack = 0 if tiny else (5, 20, 60)[index % 3]
    tasks, blocks, edges, busy = [], [], [], []
    cursor = 0
    for position in range(count):
        slots = rng.randint(1, 2) if tiny else rng.randint(2, 5)
        start, end = cursor, cursor + slots
        cursor = end + gap
        if gap:
            busy.append((end, end + gap))
        task_id = uuid5(owner, f"task/{position}")
        deadline_slot = min(horizon, end + slack) if tiny or position % 5 else None
        release_slot = max(0, start - slack * 2) if position % 4 == 0 else 0
        if mode == "infeasible" and position == 0:
            deadline_slot, release_slot = 1, 0
        deadline_at = (
            CLOCK + timedelta(minutes=15 * deadline_slot) if deadline_slot is not None else None
        )
        spec = TaskSpec(
            id=task_id,
            owner_id=owner,
            title=f"Synthetic task {position}",
            remaining_minutes=slots * 15,
            priority=rng.randint(1, 5),
            release_slot=release_slot,
            release_at=CLOCK + timedelta(minutes=15 * release_slot),
            deadline_slot=deadline_slot,
            deadline_at=deadline_at,
            deadline=Deadline(kind="TIMESTAMP", value=deadline_at.isoformat())
            if deadline_at
            else None,
            splittable=(position % 3 != 0),
            min_block_slots=1 if tiny else 2,
            max_block_slots=max(2, slots),
            short_final_allowed=not tiny,
        )
        tasks.append(spec)
        locked = position < int(count * locked_fraction) and mode != "infeasible"
        blocks.append(
            Block(
                id=uuid5(owner, f"block/{position}"),
                owner_id=owner,
                task_id=task_id,
                start=CLOCK + timedelta(minutes=15 * start),
                end=CLOCK + timedelta(minutes=15 * end),
                start_slot=start,
                end_slot=end,
                locked=locked,
                source="BENCHMARK_WITNESS",
            )
        )
        if position and rng.random() < dependency_rate:
            edges.append(
                Dependency(
                    owner_id=owner, predecessor_id=tasks[position - 1].id, successor_id=task_id
                )
            )
    end_free = min(horizon, cursor + slack + 8)
    prior_fraction = 0 if tiny else (index % 4) * 0.1
    prior = (
        Candidate(
            snapshot_hash="synthetic-prior-input",
            planning_revision=0,
            status="FEASIBLE",
            source_policy="SYNTHETIC_PREVIOUS_INPUT",
            blocks=tuple(blocks[: int(count * prior_fraction)]),
        )
        if prior_fraction
        else None
    )
    snapshot = InputSnapshot(
        id=UUID(int=0),
        snapshot_hash="",
        owner_id=owner,
        planning_revision=1,
        reference_now=CLOCK,
        timezone="UTC",
        slot_origin=CLOCK,
        horizon_start=CLOCK,
        horizon_end=CLOCK + timedelta(minutes=15 * horizon),
        horizon_start_slot=0,
        horizon_end_slot=horizon,
        tasks=tuple(tasks),
        dependencies=tuple(edges),
        availability=((0, end_free),),
        busy_slot_ranges=tuple(busy),
        protected_blocks=tuple(b for b in blocks if b.locked),
        preferred_windows=((end_free // 3, end_free),) if not tiny and index % 2 else (),
        prior_candidate=prior,
    )
    snapshot = digest_snapshot(snapshot)
    witness = Candidate(
        snapshot_hash=snapshot.snapshot_hash,
        planning_revision=1,
        status="FEASIBLE",
        source_policy="CONSTRUCTED_WITNESS",
        blocks=tuple(blocks),
    )
    violations = validate_candidate(snapshot, witness)
    if mode != "infeasible" and violations:
        raise ValueError(f"Generator witness invalid: {index}: {[v.code for v in violations]}")
    witness = witness.model_copy(update={"score": score_candidate(snapshot, witness)})
    return {
        "scenario_id": f"scenario_{index:04d}",
        "group_id": f"base_{index:04d}",
        "split": split,
        "seed": seed + index * 104729,
        "generator_version": VERSION,
        "family": mode,
        "parameters": {
            "task_count": count,
            "slack_slots": slack,
            "fragmented": fragmented,
            "locked_fraction": locked_fraction,
            "dependency_rate": dependency_rate,
            "prior_fraction": prior_fraction,
            "robustness_unseen_combination": robustness,
            "horizon_slots": horizon,
        },
        "known_feasible": mode != "infeasible",
        "feasibility_provenance": "independent validator accepted constructed witness"
        if mode != "infeasible"
        else "required first task needs >=2 slots before deadline slot1",
        "snapshot": snapshot.model_dump(mode="json", exclude_computed_fields=True),
        "witness": witness.model_dump(mode="json", exclude_computed_fields=True)
        if mode != "infeasible"
        else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path(".runtime/benchmarks/scenarios-v1.jsonl")
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output already exists; preserve immutable workload artifacts")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for index in range(1000):
            stream.write(json.dumps(generate_scenario(index), sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "path": str(args.output),
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "groups": 1000,
            }
        )
    )


if __name__ == "__main__":
    main()
