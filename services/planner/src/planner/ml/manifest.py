"""Trusted, bounded JSON artifacts; inference never unpickles model objects."""

import hashlib
from math import exp, isfinite
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planner.ml.features import FEATURE_NAMES, FEATURE_VERSION, FeatureVector


class ArtifactValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Tree(ArtifactValue):
    left: tuple[int, ...] = Field(min_length=1, max_length=2047)
    right: tuple[int, ...] = Field(min_length=1, max_length=2047)
    feature: tuple[int, ...] = Field(min_length=1, max_length=2047)
    threshold: tuple[float, ...] = Field(min_length=1, max_length=2047)
    value: tuple[float, ...] = Field(min_length=1, max_length=2047)

    @model_validator(mode="after")
    def structure(self):
        n = len(self.left)
        if any(
            len(values) != n for values in (self.right, self.feature, self.threshold, self.value)
        ):
            raise ValueError("TREE_SHAPE_MISMATCH")
        for index, (left, right, feature) in enumerate(
            zip(self.left, self.right, self.feature, strict=True)
        ):
            if left == right == -1:
                if feature != -2:
                    raise ValueError("TREE_LEAF_INVALID")
            elif not (index < left < n and index < right < n and 0 <= feature < len(FEATURE_NAMES)):
                raise ValueError("TREE_STRUCTURE_INVALID")
        return self

    def predict(self, values):
        index = 0
        while self.left[index] != -1:
            index = (
                self.left[index]
                if values[self.feature[index]] <= self.threshold[index]
                else self.right[index]
            )
        return self.value[index]


class ModelArtifact(ArtifactValue):
    version: Literal["portable-routing-v1"] = "portable-routing-v1"
    kind: Literal["logistic", "gradient_boosted"]
    feature_version: Literal["routing-features-v1"] = FEATURE_VERSION
    feature_names: tuple[str, ...] = FEATURE_NAMES
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coefficient: tuple[float, ...] = ()
    intercept: float
    learning_rate: float = Field(default=1, gt=0, le=1)
    trees: tuple[Tree, ...] = Field(default=(), max_length=200)

    @model_validator(mode="after")
    def shapes(self):
        if self.feature_names != FEATURE_NAMES or self.feature_version != FEATURE_VERSION:
            raise ValueError("FEATURE_SCHEMA_MISMATCH")
        if (
            len(self.mean) != len(FEATURE_NAMES)
            or len(self.scale) != len(FEATURE_NAMES)
            or any(value <= 0 for value in self.scale)
        ):
            raise ValueError("PREPROCESSING_INVALID")
        if self.kind == "logistic" and (len(self.coefficient) != len(FEATURE_NAMES) or self.trees):
            raise ValueError("LOGISTIC_SHAPE_INVALID")
        if self.kind == "gradient_boosted" and (not self.trees or self.coefficient):
            raise ValueError("BOOSTED_SHAPE_INVALID")
        return self

    def probability(self, features: FeatureVector) -> float:
        values = [
            (value - center) / scale
            for value, center, scale in zip(features.values, self.mean, self.scale, strict=True)
        ]
        if self.kind == "logistic":
            score = self.intercept + sum(
                value * coefficient
                for value, coefficient in zip(values, self.coefficient, strict=True)
            )
        else:
            # sklearn decision trees evaluate float32 features internally.
            import struct

            values = [struct.unpack("f", struct.pack("f", value))[0] for value in values]
            score = self.intercept + self.learning_rate * sum(
                tree.predict(values) for tree in self.trees
            )
        if not isfinite(score):
            raise ValueError("NONFINITE_MODEL_OUTPUT")
        return 1 / (1 + exp(-max(-700, min(700, score))))


def load_artifact(path: Path, expected_sha256: str, trusted_root: Path) -> ModelArtifact:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(trusted_root.resolve(strict=True)):
        raise ValueError("UNTRUSTED_ARTIFACT")
    if resolved.stat().st_size > 4_000_000:
        raise ValueError("ARTIFACT_TOO_LARGE")
    raw = resolved.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("ARTIFACT_HASH_MISMATCH")
    return ModelArtifact.model_validate_json(raw)
