from pathlib import Path

from planner.ml import router
from planner.solver.greedy import greedy_schedule
from tests.fixtures.builders import snapshot


def test_bad_artifact_rolls_back_to_fixed_solver(monkeypatch, tmp_path):
    spec = snapshot()
    expected = greedy_schedule(spec)
    calls = []
    monkeypatch.setattr(router, "solve_cp_sat", lambda *a, **k: calls.append(k) or expected)
    candidate = router.solve_routed(
        spec,
        config=router.RoutingConfig(
            mode="learned",
            release_path=tmp_path / "missing.json",
            release_sha256="wrong",
            trusted_root=tmp_path,
        ),
    )
    assert candidate == expected
    assert calls[0]["budget_ms"] == 2000


def test_unpromoted_release_is_not_served(tmp_path):
    import hashlib
    import json

    import pytest

    path = tmp_path / "release.json"
    path.write_text(json.dumps({"promote": False}), encoding="utf-8")
    config = router.RoutingConfig(
        mode="learned",
        release_path=path,
        release_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        trusted_root=Path(tmp_path),
    )
    with pytest.raises(ValueError, match="NOT_PROMOTED"):
        router.load_release(config)
