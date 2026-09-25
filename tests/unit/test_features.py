"""Features depend only on inputs and the already computed greedy candidate."""

import math

import pytest

from planner.ml.features import FEATURE_NAMES, FeatureVector, build_features
from planner.solver.greedy import greedy_schedule
from tests.fixtures.builders import snapshot


def test_features_are_finite_ordered_and_deterministic():
    spec = snapshot()
    greedy = greedy_schedule(spec)
    features = build_features(spec, greedy)
    assert features.names == FEATURE_NAMES
    assert features == build_features(spec, greedy)
    assert all(math.isfinite(value) for value in features.values)
    assert features.as_dict()["task_count"] == 2
    assert features.as_dict()["required_slots"] == 8
    assert features.as_dict()["greedy_valid"] == 1


def test_no_free_time_is_a_finite_invalid_greedy_case():
    spec = snapshot(availability=())
    features = build_features(spec, greedy_schedule(spec))
    assert features.as_dict()["free_slots"] == 0
    assert features.as_dict()["greedy_valid"] == 0
    assert all(math.isfinite(value) for value in features.values)


def test_feature_vectors_reject_nonfinite_values_and_wrong_order():
    with pytest.raises(ValueError):
        FeatureVector(FEATURE_NAMES, tuple(float("nan") for _ in FEATURE_NAMES))
    with pytest.raises(ValueError):
        FeatureVector(tuple(reversed(FEATURE_NAMES)), tuple(0.0 for _ in FEATURE_NAMES))
