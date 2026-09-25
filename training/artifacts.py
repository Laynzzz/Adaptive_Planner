"""Export fitted sklearn baselines to constrained, inspectable serving data."""

from math import log

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from planner.ml.manifest import ModelArtifact, Tree


def export_pipeline(pipeline) -> ModelArtifact:
    scaler, model = pipeline.steps[0][1], pipeline.steps[1][1]
    if (
        not isinstance(scaler, StandardScaler)
        or not scaler.with_mean
        or not scaler.with_std
        or list(model.classes_) != [0, 1]
    ):
        raise ValueError("Unsupported preprocessing or label order")
    common = dict(mean=tuple(scaler.mean_), scale=tuple(scaler.scale_))
    if isinstance(model, LogisticRegression):
        return ModelArtifact(
            kind="logistic",
            **common,
            coefficient=tuple(model.coef_[0]),
            intercept=float(model.intercept_[0]),
        )
    if isinstance(model, GradientBoostingClassifier):
        if model.loss != "log_loss" or model.init is not None:
            raise ValueError("Unsupported boosting loss or initializer")
        prior = float(model.init_.class_prior_[1])
        trees = []
        for estimator in model.estimators_[:, 0]:
            tree = estimator.tree_
            trees.append(
                Tree(
                    left=tuple(int(value) for value in tree.children_left),
                    right=tuple(int(value) for value in tree.children_right),
                    feature=tuple(int(value) for value in tree.feature),
                    threshold=tuple(tree.threshold),
                    value=tuple(tree.value[:, 0, 0]),
                )
            )
        return ModelArtifact(
            kind="gradient_boosted",
            **common,
            intercept=log(prior / (1 - prior)),
            learning_rate=model.learning_rate,
            trees=tuple(trees),
        )
    raise ValueError("Unsupported model type")
