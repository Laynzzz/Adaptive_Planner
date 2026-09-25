from training.build_dataset import label_case


def test_timeout_without_better_plan_is_unknown_not_negative():
    greedy = {"validated": True, "quality": 0.8}
    reference = {"validated": True, "quality": 0.8, "proof": None, "status": "FEASIBLE"}
    assert label_case(greedy, reference)["label"] is None


def test_only_measured_improvement_or_optimality_assigns_label():
    greedy = {"validated": True, "quality": 0.8}
    assert label_case(greedy, {"validated": True, "quality": 0.83, "proof": None})["label"] is True
    assert (
        label_case(greedy, {"validated": True, "quality": 0.81, "proof": "CP_SAT_OPTIMAL"})["label"]
        is False
    )
    assert (
        label_case({"validated": False, "quality": None}, {"validated": True, "quality": 0.9})[
            "label"
        ]
        is None
    )


def test_summary_retains_timeouts_and_invalid_results_in_counts():
    from benchmarks.analyze import summarize_policy

    rows = [
        {
            "known_feasible": True,
            "reference": {"validated": True, "quality": 0.9},
            "results": [
                {
                    "policy": "greedy",
                    "validated": True,
                    "invalid": False,
                    "quality": 0.8,
                    "status": "FEASIBLE",
                    "total_ms": 10,
                    "timings": {},
                },
                {
                    "policy": "greedy",
                    "validated": False,
                    "invalid": False,
                    "quality": None,
                    "status": "TIMEOUT",
                    "total_ms": 20,
                    "timings": {},
                },
                {
                    "policy": "greedy",
                    "validated": False,
                    "invalid": True,
                    "quality": None,
                    "status": "FEASIBLE",
                    "total_ms": 30,
                    "timings": {},
                },
            ],
        }
    ]
    result = summarize_policy(rows, "greedy")
    assert result["runs"] == result["known_feasible_runs"] == 3
    assert result["completed_valid"] == result["known_feasible_completed"] == 1
    assert result["invalid"] == 1
    assert result["missing_or_invalid"] == 2
    assert result["paired_quality"]["n"] == 1
    assert abs(result["paired_quality"]["mean_positive_loss"] - 0.1) < 1e-9
    assert result["end_to_end_ms"]["n"] == 3


def test_measure_deadline_cleans_real_grandchild(tmp_path):
    import os
    import subprocess
    import time

    import pytest

    from benchmarks.run import measure

    if os.name != "nt":
        pytest.skip("Windows redirector-specific regression")
    package = tmp_path / "benchmarks"
    package.mkdir()
    (package / "__init__.py").write_text("")
    marker, child_pid = tmp_path / "escaped.txt", tmp_path / "child.pid"
    grandchild = (
        "import pathlib,time; time.sleep(0.9); pathlib.Path("
        + repr(str(marker))
        + ").write_text('escaped')"
    )
    (package / "child.py").write_text(
        "import os,pathlib,subprocess,sys,time\n"
        + "pathlib.Path("
        + repr(str(child_pid))
        + ").write_text(str(os.getpid()))\n"
        + 'subprocess.Popen([sys.executable, "-c", '
        + repr(grandchild)
        + "])\n"
        + "time.sleep(3)\n"
    )
    try:
        result = measure(
            {"snapshot": {}, "family": "test"},
            "greedy",
            budget_ms=0,
            wall_ms=350,
            seed=1,
            frozen_path=tmp_path,
        )
        assert result["error"] == "WALL_TIMEOUT"
        assert child_pid.exists(), "Child must start so the regression exercises real descendants"
        time.sleep(1.1)
        assert not marker.exists(), "A descendant continued after the benchmark deadline"
    finally:
        if child_pid.exists():
            subprocess.run(
                ["taskkill", "/PID", child_pid.read_text(), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
