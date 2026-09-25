"""One measured policy execution in a fresh, bounded subprocess."""

import json
import sys
from pathlib import Path
from time import perf_counter, process_time

BOOT = perf_counter()
CPU_BOOT = process_time()


def rss_bytes():
    import ctypes
    from ctypes import wintypes

    if sys.platform != "win32":
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    get_current = ctypes.windll.kernel32.GetCurrentProcess
    get_current.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    if not get_memory(get_current(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return counters.PeakWorkingSetSize


def execute(request):
    from planner.domain.contracts import InputSnapshot
    from planner.solver import cp_sat
    from planner.solver.greedy import greedy_schedule
    from planner.solver.validator import validate_candidate

    startup_ms = (perf_counter() - BOOT) * 1000
    snapshot = InputSnapshot.model_validate(request["snapshot"])
    timings = {
        "startup_import_ms": startup_ms,
        "greedy_ms": 0.0,
        "feature_ms": None,
        "model_build_ms": 0.0,
        "native_solve_ms": 0.0,
        "validation_ms": 0.0,
    }
    original_build, original_run = cp_sat.build_model, cp_sat._run

    def build(*args, **kwargs):
        start = perf_counter()
        output = original_build(*args, **kwargs)
        timings["model_build_ms"] += (perf_counter() - start) * 1000
        return output

    def native(*args, **kwargs):
        start = perf_counter()
        output = original_run(*args, **kwargs)
        timings["native_solve_ms"] += (perf_counter() - start) * 1000
        return output

    cp_sat.build_model, cp_sat._run = build, native
    policy = request["policy"]
    budget = request["budget_ms"]
    greedy = features = None
    if policy in ("greedy", "warm_cp_sat", "reference"):
        start = perf_counter()
        greedy = greedy_schedule(snapshot)
        timings["greedy_ms"] = (perf_counter() - start) * 1000
        try:
            from planner.ml.features import build_features
        except ImportError:
            pass
        else:
            start = perf_counter()
            features = build_features(snapshot, greedy)
            timings["feature_ms"] = (perf_counter() - start) * 1000
            if hasattr(features, "as_dict"):
                features = features.as_dict()
            elif hasattr(features, "model_dump"):
                features = features.model_dump(mode="json")
            elif hasattr(features, "__dict__"):
                features = dict(features.__dict__)
    if policy == "greedy":
        candidate = greedy
    elif policy in ("warm_cp_sat", "reference"):
        remaining = max(0, budget - int(timings["greedy_ms"] + (timings["feature_ms"] or 0)))
        candidate = cp_sat.solve_cp_sat(
            snapshot,
            remaining,
            request["seed"],
            warm_candidate=greedy,
            use_greedy_hint=True,
            allow_greedy_fallback=True,
        )
    else:
        candidate = cp_sat.solve_cp_sat(
            snapshot, budget, request["seed"], use_greedy_hint=False, allow_greedy_fallback=False
        )
    start = perf_counter()
    violations = (
        validate_candidate(snapshot, candidate)
        if candidate.status in ("FEASIBLE", "OPTIMAL")
        else []
    )
    timings["validation_ms"] = (perf_counter() - start) * 1000
    valid = candidate.status in ("FEASIBLE", "OPTIMAL") and not violations
    result = {
        "status": candidate.status,
        "validated": valid,
        "invalid": bool(violations),
        "quality": candidate.score.quality if valid and candidate.score else None,
        "candidate": candidate.model_dump(mode="json", exclude_computed_fields=True),
        "greedy_candidate": greedy.model_dump(mode="json", exclude_computed_fields=True)
        if greedy
        else None,
        "features": features,
        "timings": timings,
        "child_cpu_ms": (process_time() - CPU_BOOT) * 1000,
        "child_wall_ms": (perf_counter() - BOOT) * 1000,
        "peak_rss_bytes": rss_bytes(),
        "native_budget_ms": budget,
        "error": None,
        "proof": "CP_SAT_OPTIMAL" if candidate.status == "OPTIMAL" else None,
    }
    if policy == "reference" and request.get("tiny_exact"):
        from benchmarks.tiny_reference import enumerate_candidates

        start = perf_counter()
        exact = max(enumerate_candidates(snapshot), key=lambda c: c.score.quality, default=None)
        result["exact_enumeration_ms"] = (perf_counter() - start) * 1000
        if exact is not None:
            exact = exact.model_copy(update={"status": "OPTIMAL"})
            result.update(
                status="OPTIMAL",
                validated=True,
                invalid=False,
                quality=exact.score.quality,
                candidate=exact.model_dump(mode="json", exclude_computed_fields=True),
                proof="EXHAUSTIVE_TINY",
            )
        else:
            result.update(
                status="INFEASIBLE",
                validated=False,
                invalid=False,
                quality=None,
                candidate=None,
                proof="EXHAUSTIVE_TINY",
            )
        result["child_cpu_ms"] = (process_time() - CPU_BOOT) * 1000
        result["child_wall_ms"] = (perf_counter() - BOOT) * 1000
    return result


def main():
    request_path, output_path = map(Path, sys.argv[1:3])
    try:
        output = execute(json.loads(request_path.read_text(encoding="utf-8")))
    except Exception as error:
        output = {
            "status": "ERROR",
            "validated": False,
            "invalid": False,
            "quality": None,
            "candidate": None,
            "error": type(error).__name__ + ": " + str(error)[:300],
        }
    output_path.write_text(json.dumps(output, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
