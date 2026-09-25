"""Conservative routing with a hash-pinned release and immediate fixed-policy rollback."""

import hashlib
import json
import os
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Literal

from planner.ml.features import build_features
from planner.ml.manifest import load_artifact
from planner.solver.cp_sat import solve_cp_sat
from planner.solver.greedy import greedy_schedule
from planner.solver.validator import validate_candidate


@dataclass(frozen=True)
class RoutingConfig:
    mode: Literal["fixed", "shadow", "learned"] = "fixed"
    release_path: Path | None = None
    release_sha256: str = ""
    trusted_root: Path | None = None

    @classmethod
    def from_environment(cls):
        mode = os.getenv("PLANNER_ROUTING_MODE", "fixed")
        return cls(
            mode=mode if mode in ("fixed", "shadow", "learned") else "fixed",
            release_path=Path(os.environ["PLANNER_ROUTING_RELEASE"])
            if os.getenv("PLANNER_ROUTING_RELEASE")
            else None,
            release_sha256=os.getenv("PLANNER_ROUTING_RELEASE_SHA256", ""),
            trusted_root=Path(os.environ["PLANNER_ROUTING_TRUSTED_ROOT"])
            if os.getenv("PLANNER_ROUTING_TRUSTED_ROOT")
            else None,
        )


def load_release(config):
    if config.release_path is None or config.trusted_root is None:
        raise ValueError("ARTIFACT_UNAVAILABLE")
    path = config.release_path.resolve(strict=True)
    if not path.is_relative_to(config.trusted_root.resolve(strict=True)):
        raise ValueError("UNTRUSTED_RELEASE")
    if path.stat().st_size > 64_000:
        raise ValueError("RELEASE_TOO_LARGE")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != config.release_sha256:
        raise ValueError("RELEASE_HASH_MISMATCH")
    release = json.loads(raw)
    if not isinstance(release, dict):
        raise ValueError("RELEASE_SCHEMA_MISMATCH")
    if config.mode == "learned" and release.get("promote") is not True:
        raise ValueError("NOT_PROMOTED")
    if release.get("version") != "routing-release-v1":
        raise ValueError("RELEASE_VERSION_MISMATCH")
    threshold = release.get("threshold")
    budget = release.get("cp_budget_ms")
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not isfinite(threshold)
        or not 0 <= threshold <= 1
        or isinstance(budget, bool)
        or not isinstance(budget, int)
        or not 1 <= budget <= 2000
    ):
        raise ValueError("RELEASE_CONFIGURATION_INVALID")
    model = load_artifact(
        path.parent / release["model_path"], release["model_sha256"], config.trusted_root
    )
    return lambda features: model.probability(features) >= threshold, budget


def solve_routed(snapshot, *, config=None, budget_ms=2000, seed=0, observe=None):
    """Shadow makes no routing change. Every greedy shortcut is independently validated.

    The existing parent process enforces the wall deadline and owns persistence;
    no model can activate a proposal or write to the database here.
    """
    config = config or RoutingConfig.from_environment()
    started = perf_counter()
    event = {"mode": config.mode, "decision": "CP_SAT", "fallback": None}

    def finish(candidate):
        event["total_ms"] = (perf_counter() - started) * 1000
        if observe:
            observe(event)
        return candidate

    if config.mode == "fixed":
        return finish(solve_cp_sat(snapshot, budget_ms=budget_ms, seed=seed))
    try:
        chooser, release_budget = load_release(config)
        greedy = greedy_schedule(snapshot)
        features = build_features(snapshot, greedy)
        valid = greedy.status in ("FEASIBLE", "OPTIMAL") and not validate_candidate(
            snapshot, greedy
        )
        escalate = not valid or chooser(features)
        event["decision"] = "CP_SAT" if escalate else "GREEDY"
        if config.mode == "shadow":
            return finish(solve_cp_sat(snapshot, budget_ms=budget_ms, seed=seed))
        if not escalate:
            return finish(greedy)
        remaining = max(0, min(budget_ms, release_budget) - int((perf_counter() - started) * 1000))
        return finish(solve_cp_sat(snapshot, budget_ms=remaining, seed=seed, warm_candidate=greedy))
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        # Deliberately exclude exception text: paths and model contents are not telemetry.
        event["fallback"] = "ARTIFACT_UNAVAILABLE"
        event["decision"] = "CP_SAT"
        return finish(solve_cp_sat(snapshot, budget_ms=budget_ms, seed=seed))
