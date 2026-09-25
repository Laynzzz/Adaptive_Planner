"""Frozen mock pipeline run. This command never enables or invokes a paid provider."""

import argparse
import asyncio
import hashlib
import json
import platform
import random
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from evals.data.check import DATA, load_frozen
from evals.score.metrics import flatten, score
from planner.ai.interpret import parse_proposal
from planner.ai.provider import Context, MockProvider


def family_interval(records):
    """Descriptive grouped bootstrap; synthetic small data does not establish real quality."""
    families = sorted({row["family"] for row in records})
    groups = {family: [row for row in records if row["family"] == family] for family in families}
    randomizer = random.Random(20260925)
    values = []
    for _ in range(2000):
        sample = [
            row
            for family in randomizer.choices(families, k=len(families))
            for row in groups[family]
        ]
        accuracy = score(sample)["critical_fields"]["accuracy"]
        if accuracy is not None:
            values.append(accuracy)
    values.sort()
    return (
        [values[int(len(values) * 0.025)], values[min(len(values) - 1, int(len(values) * 0.975))]]
        if values
        else None
    )


async def evaluate(rows):
    records = []
    for row in rows:
        start = perf_counter()
        error = proposal = prediction = None
        try:
            result = await MockProvider().extract(
                Context(row["text"], datetime.fromisoformat(row["reference_now"]), row["timezone"])
            )
            proposal = parse_proposal(result.payload_json, row["text"])
            prediction = flatten(proposal)
        except (ValueError, KeyError) as failure:
            error = type(failure).__name__ + ": " + str(failure)[:300]
        records.append(
            {
                "id": row["id"],
                "family": row["family"],
                "category": row["category"],
                "reference": row["reference"],
                "prediction": prediction,
                "proposal": proposal.model_dump(mode="json") if proposal else None,
                "schema_valid": proposal is not None,
                "error": error,
                "latency_ms": (perf_counter() - start) * 1000,
                "cost_microusd": 0,
                "provider": "mock",
                "model": "deterministic-demo-v1",
                "input_tokens": 0,
                "output_tokens": 0,
                "attempts": 1,
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "validation", "test"), required=True)
    parser.add_argument("--mode", choices=("mock",), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest, splits = load_frozen()
    records = asyncio.run(evaluate(splits[args.split]))
    report = {
        "run_at": datetime.now(UTC).isoformat(),
        "mode": args.mode,
        "split": args.split,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "manifest_hash": hashlib.sha256((DATA / "manifest.json").read_bytes()).hexdigest(),
        "prompt_hash": manifest["prompt_hash"],
        "schema_hash": manifest["schema_hash"],
        "model_config_hash": manifest["model_config_hash"],
        "data_hash": manifest["files"][args.split + ".jsonl"]["sha256"],
        "quality_claim": (
            "MOCK PIPELINE ONLY; real AI quality and independent human reference review unexecuted"
        ),
        "metrics": score(records),
        "family_bootstrap_95": family_interval(records),
        "by_category": {
            category: score([r for r in records if r["category"] == category])
            for category in sorted({r["category"] for r in records})
        },
        "records": records,
    }
    output = args.output or Path("docs/evidence/raw") / f"ai-mock-{args.split}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit("Output exists; choose a new --output path to preserve prior evidence.")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "metrics": report["metrics"],
                "family_bootstrap_95": report["family_bootstrap_95"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
