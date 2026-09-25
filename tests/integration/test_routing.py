from planner.ml import router
from planner.solver.greedy import greedy_schedule
from tests.fixtures.builders import snapshot


def test_fixed_and_shadow_return_same_candidate_without_external_state(monkeypatch):
    spec = snapshot()
    expected = greedy_schedule(spec)
    calls = []
    monkeypatch.setattr(router, "solve_cp_sat", lambda *a, **k: calls.append(k) or expected)
    fixed = router.solve_routed(spec, config=router.RoutingConfig())
    events = []
    shadow = router.solve_routed(
        spec, config=router.RoutingConfig(mode="shadow"), observe=events.append
    )
    assert fixed == shadow == expected
    assert len(calls) == 2
    assert events[-1]["fallback"] == "ARTIFACT_UNAVAILABLE"


def test_validator_veto_forces_solver_even_when_model_accepts(monkeypatch):
    spec = snapshot(availability=())
    calls = []
    monkeypatch.setattr(router, "load_release", lambda config: (lambda features: False, 200))
    monkeypatch.setattr(
        router, "solve_cp_sat", lambda *a, **k: calls.append(k) or greedy_schedule(spec)
    )
    router.solve_routed(spec, config=router.RoutingConfig(mode="learned"))
    assert len(calls) == 1


def test_real_json_routing_and_shadow_have_serving_feature_parity(tmp_path):
    import hashlib
    import json

    from planner.ml.features import FEATURE_NAMES
    from planner.ml.manifest import ModelArtifact
    from planner.solver.validator import validate_candidate

    model = ModelArtifact(
        kind="logistic",
        mean=(0.0,) * len(FEATURE_NAMES),
        scale=(1.0,) * len(FEATURE_NAMES),
        coefficient=(0.0,) * len(FEATURE_NAMES),
        intercept=-10,
    )
    model_path = tmp_path / "model.json"
    model_path.write_text(model.model_dump_json(), encoding="utf-8")
    release_path = tmp_path / "release.json"
    release_path.write_text(
        json.dumps(
            {
                "version": "routing-release-v1",
                "promote": True,
                "model_path": "model.json",
                "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                "threshold": 0.5,
                "cp_budget_ms": 200,
            }
        ),
        encoding="utf-8",
    )
    common = dict(
        release_path=release_path,
        release_sha256=hashlib.sha256(release_path.read_bytes()).hexdigest(),
        trusted_root=tmp_path,
    )
    spec = snapshot()
    events = []
    learned = router.solve_routed(
        spec, config=router.RoutingConfig(mode="learned", **common), observe=events.append
    )
    assert learned.source_policy == "GREEDY"
    assert not validate_candidate(spec, learned)
    assert events[-1]["decision"] == "GREEDY"
    shadow = router.solve_routed(
        spec,
        config=router.RoutingConfig(mode="shadow", **common),
        budget_ms=200,
        observe=events.append,
    )
    fixed = router.solve_routed(spec, config=router.RoutingConfig(), budget_ms=200)
    assert shadow.blocks == fixed.blocks
    assert shadow.status == fixed.status
    assert shadow.score == fixed.score
    assert events[-1]["decision"] == "GREEDY"
