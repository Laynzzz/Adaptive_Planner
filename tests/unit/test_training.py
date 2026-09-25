import pytest

from planner.ml.features import FEATURE_NAMES
from training.train import fit_candidates, validate_splits


def row(i, split="train", label=None):
    return {
        "group_id": str(i),
        "split": split,
        "label": label,
        "features": {key: float(i) for key in FEATURE_NAMES},
    }


def test_preprocessing_fits_only_known_training_rows():
    rows = [row(i, label=bool(i % 2)) for i in range(10)]
    rows.append(row(10000, label=None))
    models = fit_candidates(rows, seed=3)
    assert set(models) == {"logistic", "gradient_boosted"}
    for artifact in models.values():
        assert artifact.mean == pytest.approx([4.5] * len(FEATURE_NAMES))


def test_training_rejects_validation_rows_and_group_leakage():
    with pytest.raises(ValueError, match="TRAIN_ONLY"):
        fit_candidates([row(1, "validation", True)], seed=3)
    with pytest.raises(ValueError, match="GROUP_LEAKAGE"):
        validate_splits([row(1)], [row(1, "validation")])


def test_single_class_is_explicitly_untrainable():
    with pytest.raises(ValueError, match="INSUFFICIENT_TRAIN_LABELS"):
        fit_candidates([row(i, label=False) for i in range(5)], seed=3)
