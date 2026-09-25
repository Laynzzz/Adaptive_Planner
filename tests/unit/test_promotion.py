from dataclasses import replace

import pytest

from training.promote import PromotionMetrics, evaluate_promotion


@pytest.fixture
def metrics():
    return PromotionMetrics(
        test_count=200,
        paired_valid_count=180,
        invalid_accepted=0,
        reference_completion_losses=0,
        simple_completion_losses=0,
        mean_quality_loss=0.02,
        worst_decile_quality_loss=0.05,
        always_solver_p95_gain=0.20,
        simple_router_p95_gain=0.10,
        simple_router_mean_loss_difference=0.005,
        paired_latency_improvement_ci=(1.0, 12.0),
    )


def test_exact_positive_gate_boundaries_pass(metrics):
    assert evaluate_promotion(metrics).promote


@pytest.mark.parametrize(
    "change,code",
    [
        ({"always_solver_p95_gain": 0.25, "simple_router_p95_gain": 0}, "SIMPLE_P95_GAIN"),
        ({"invalid_accepted": 1}, "INVALID_ACCEPTED_PLAN"),
        ({"reference_completion_losses": 1}, "REFERENCE_COMPLETION_LOSS"),
        ({"simple_completion_losses": 1}, "SIMPLE_COMPLETION_LOSS"),
        ({"mean_quality_loss": 0.02001}, "MEAN_QUALITY_LOSS"),
        ({"worst_decile_quality_loss": 0.05001}, "TAIL_QUALITY_LOSS"),
        ({"always_solver_p95_gain": 0.1999}, "ALWAYS_CP_P95_GAIN"),
        ({"simple_router_mean_loss_difference": 0.00501}, "SIMPLE_QUALITY_LOSS"),
        ({"paired_latency_improvement_ci": (0.0, 12.0)}, "LATENCY_UNCERTAINTY"),
        ({"paired_valid_count": 0}, "INSUFFICIENT_EVIDENCE"),
        ({"mean_quality_loss": float("nan")}, "INVALID_METRICS"),
    ],
)
def test_each_failed_gate_prevents_promotion(metrics, change, code):
    decision = evaluate_promotion(replace(metrics, **change))
    assert not decision.promote
    assert code in decision.failed_gates
