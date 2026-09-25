"""Independent, frozen acceptance gates from plan section 13."""

from dataclasses import dataclass
from math import isfinite


@dataclass
class PromotionMetrics:
    test_count: int
    paired_valid_count: int
    invalid_accepted: int
    reference_completion_losses: int
    simple_completion_losses: int
    mean_quality_loss: float
    worst_decile_quality_loss: float
    always_solver_p95_gain: float
    simple_router_p95_gain: float
    simple_router_mean_loss_difference: float
    paired_latency_improvement_ci: tuple[float, float]


@dataclass(frozen=True)
class PromotionDecision:
    promote: bool
    failed_gates: tuple[str, ...]


def evaluate_promotion(metrics: PromotionMetrics) -> PromotionDecision:
    counts = (
        metrics.test_count,
        metrics.paired_valid_count,
        metrics.invalid_accepted,
        metrics.reference_completion_losses,
        metrics.simple_completion_losses,
    )
    values = (
        metrics.mean_quality_loss,
        metrics.worst_decile_quality_loss,
        metrics.always_solver_p95_gain,
        metrics.simple_router_p95_gain,
        metrics.simple_router_mean_loss_difference,
        *metrics.paired_latency_improvement_ci,
    )
    if (
        any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts)
        or not all(isfinite(value) for value in values)
        or metrics.paired_latency_improvement_ci[0] > metrics.paired_latency_improvement_ci[1]
        or metrics.paired_valid_count > metrics.test_count
        or metrics.mean_quality_loss < 0
        or metrics.worst_decile_quality_loss < 0
    ):
        return PromotionDecision(False, ("INVALID_METRICS",))
    gates = (
        (metrics.test_count > 0 and metrics.paired_valid_count > 0, "INSUFFICIENT_EVIDENCE"),
        (metrics.invalid_accepted == 0, "INVALID_ACCEPTED_PLAN"),
        (metrics.reference_completion_losses == 0, "REFERENCE_COMPLETION_LOSS"),
        (metrics.simple_completion_losses == 0, "SIMPLE_COMPLETION_LOSS"),
        (metrics.mean_quality_loss <= 0.02, "MEAN_QUALITY_LOSS"),
        (metrics.worst_decile_quality_loss <= 0.05, "TAIL_QUALITY_LOSS"),
        (metrics.always_solver_p95_gain >= 0.20, "ALWAYS_CP_P95_GAIN"),
        (metrics.simple_router_p95_gain >= 0.10, "SIMPLE_P95_GAIN"),
        (metrics.simple_router_mean_loss_difference <= 0.005, "SIMPLE_QUALITY_LOSS"),
        (metrics.paired_latency_improvement_ci[0] > 0, "LATENCY_UNCERTAINTY"),
    )
    failed = tuple(code for passed, code in gates if not passed)
    return PromotionDecision(not failed, failed)
