import hashlib
import json

import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from planner.ml.features import FEATURE_NAMES, FeatureVector
from planner.ml.manifest import load_artifact
from training.artifacts import export_pipeline


@pytest.mark.parametrize(
    "estimator",
    [
        LogisticRegression(random_state=7),
        GradientBoostingClassifier(n_estimators=8, max_depth=2, random_state=7),
    ],
)
def test_portable_json_matches_fitted_probability_without_loading_executable_objects(
    tmp_path, estimator
):
    random = np.random.default_rng(7)
    x = random.normal(size=(50, len(FEATURE_NAMES)))
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    fitted = make_pipeline(StandardScaler(), estimator).fit(x[:40], y[:40])
    artifact = export_pipeline(fitted)
    path = tmp_path / "model.json"
    path.write_text(artifact.model_dump_json(), encoding="utf-8")
    model = load_artifact(path, hashlib.sha256(path.read_bytes()).hexdigest(), tmp_path)
    for row, expected in zip(x[40:], fitted.predict_proba(x[40:])[:, 1], strict=True):
        assert model.probability(FeatureVector(FEATURE_NAMES, tuple(row))) == pytest.approx(
            expected, abs=1e-12
        )
    assert model.mean == tuple(x[:40].mean(axis=0))


def test_artifact_hash_and_trusted_directory_are_required(tmp_path):
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"kind": "anything"}), encoding="utf-8")
    with pytest.raises(ValueError, match="UNTRUSTED_ARTIFACT"):
        load_artifact(outside, hashlib.sha256(outside.read_bytes()).hexdigest(), trusted)
    path = trusted / "model.json"
    path.write_bytes(outside.read_bytes())
    with pytest.raises(ValueError, match="ARTIFACT_HASH_MISMATCH"):
        load_artifact(path, "0" * 64, trusted)


@pytest.mark.parametrize(
    "scaler", [StandardScaler(with_mean=False), StandardScaler(with_std=False)]
)
def test_export_rejects_preprocessing_that_the_artifact_does_not_represent(scaler):
    x = np.random.default_rng(9).normal(size=(30, len(FEATURE_NAMES))) + 2
    y = (x[:, 0] > 2).astype(int)
    pipeline = make_pipeline(scaler, LogisticRegression()).fit(x, y)
    with pytest.raises(ValueError, match="Unsupported preprocessing"):
        export_pipeline(pipeline)


def test_export_rejects_boosting_link_that_the_artifact_does_not_represent():
    x = np.random.default_rng(9).normal(size=(30, len(FEATURE_NAMES)))
    y = (x[:, 0] > 0).astype(int)
    pipeline = make_pipeline(
        StandardScaler(),
        GradientBoostingClassifier(loss="exponential", n_estimators=5, max_depth=2, random_state=9),
    ).fit(x, y)
    with pytest.raises(ValueError, match="Unsupported boosting"):
        export_pipeline(pipeline)
