"""Bounded sidecar carries router diagnostics out of an expendable solver child."""

import json
import math


def route_path(candidate_path):
    return candidate_path.with_suffix(".telemetry.json")


def safe_route(event):
    mode = event.get("mode")
    decision = event.get("decision")
    if mode not in ("fixed", "shadow", "learned") or decision not in ("CP_SAT", "GREEDY"):
        return None
    elapsed = event.get("total_ms")
    if (
        not isinstance(elapsed, (int, float))
        or not math.isfinite(elapsed)
        or not 0 <= elapsed <= 120000
    ):
        return None
    return {
        "mode": mode,
        "decision": decision,
        "fallback": "ARTIFACT_UNAVAILABLE"
        if event.get("fallback") == "ARTIFACT_UNAVAILABLE"
        else None,
        "total_ms": elapsed,
    }


def write_route(candidate_path, event):
    bounded = safe_route(event)
    if bounded is not None:
        route_path(candidate_path).write_text(json.dumps(bounded), encoding="utf-8")


def observe_route(candidate_path):
    from planner.observability.runtime import get_telemetry, span

    try:
        with route_path(candidate_path).open("rb") as stream:
            event = safe_route(json.loads(stream.read(4097)))
    except (OSError, ValueError, TypeError):
        return
    if event is None:
        return
    with span(
        "solver.route",
        routing_mode=event["mode"],
        routing_decision=event["decision"],
        routing_fallback=event["fallback"],
    ):
        get_telemetry().measure(
            "planner.solver.duration",
            event["total_ms"] / 1000,
            stage=event["mode"],
            status=event["decision"],
        )
