"""Exact raw-count metrics; failed parses remain in reference denominators."""

from math import sqrt
from statistics import median


def flatten(proposal):
    fields, clarify = {}, set(proposal.unresolved_fields)
    for task in proposal.tasks:
        for name in ("title", "remaining_minutes", "deadline", "priority"):
            item = getattr(task, name)
            path = f"tasks.{task.key}.{name}"
            value = (
                item.value.model_dump(mode="json")
                if hasattr(item.value, "model_dump")
                else item.value
            )
            fields[path] = {"value": value, "label": item.label}
            if item.requires_confirmation:
                clarify.add(path)
        fields[f"tasks.{task.key}.predecessor_keys"] = {
            "value": list(task.predecessor_keys),
            "label": "explicit",
        }
    return {
        "fields": fields,
        "constraints": [
            {"kind": item.kind, "weekday": item.weekday} for item in proposal.constraints
        ],
        "required_clarifications": sorted(clarify),
        "abstained": proposal.abstained,
    }


def wilson(correct, total):
    if not total:
        return None
    z = 1.959963984540054
    p = correct / total
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    width = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [max(0, center - width), min(1, center + width)]


def score(records):
    critical_correct = critical_total = correct = total = missing = 0
    invented = predicted_nonnull = full = failures = 0
    tp = fp = fn = hard_correct = hard_total = extra_constraints = 0
    abstention_correct = abstention_predicted = abstention_required = 0
    known_cost = unknown_cost = 0
    unknown_reference = unknown_correct = 0
    latencies = []
    for record in records:
        reference = record["reference"]
        predicted = record["prediction"] or {
            "fields": {},
            "constraints": [],
            "required_clarifications": [],
            "abstained": False,
        }
        valid = record["schema_valid"]
        failures += not valid
        for path, field in reference["fields"].items():
            match = valid and predicted["fields"].get(path) == field
            if field["label"] == "unknown":
                unknown_reference += 1
                unknown_correct += match
            total += 1
            correct += match
            missing += path not in predicted["fields"]
            if path.rsplit(".", 1)[-1] in ("remaining_minutes", "deadline", "predecessor_keys"):
                critical_total += 1
                critical_correct += match
        for path, field in predicted["fields"].items():
            if field["value"] is not None:
                predicted_nonnull += 1
                expected = reference["fields"].get(path)
                invented += expected is None or expected["label"] == "unknown"
        expected_clarify = set(reference["required_clarifications"])
        predicted_clarify = set(predicted["required_clarifications"])
        tp += len(expected_clarify & predicted_clarify)
        fp += len(predicted_clarify - expected_clarify)
        fn += len(expected_clarify - predicted_clarify)
        remaining = list(predicted["constraints"])
        hard_total += len(reference["constraints"])
        for constraint in reference["constraints"]:
            if valid and constraint in remaining:
                hard_correct += 1
                remaining.remove(constraint)
        extra_constraints += len(remaining)
        full += (
            valid
            and predicted["fields"] == reference["fields"]
            and predicted["constraints"] == reference["constraints"]
            and expected_clarify == predicted_clarify
            and predicted["abstained"] == reference["abstained"]
        )
        abstention_correct += valid and predicted["abstained"] == reference["abstained"]
        abstention_predicted += predicted["abstained"]
        abstention_required += reference["abstained"]
        if record.get("cost_microusd") is None:
            unknown_cost += 1
        else:
            known_cost += record["cost_microusd"]
        if record.get("latency_ms") is not None:
            latencies.append(record["latency_ms"])
    latencies.sort()
    return {
        "critical_fields": {
            "correct": critical_correct,
            "total": critical_total,
            "accuracy": critical_correct / critical_total if critical_total else None,
            "wilson_95": wilson(critical_correct, critical_total),
        },
        "all_fields": {"correct": correct, "total": total, "missing": missing},
        "full_proposals": {"correct": full, "total": len(records)},
        "hard_soft": {
            "correct": hard_correct,
            "total": hard_total,
            "unmatched_predicted_constraints": extra_constraints,
        },
        "unknown_fields": {"correct": unknown_correct, "reference_total": unknown_reference},
        "invented_fields": {"count": invented, "predicted_nonnull_fields": predicted_nonnull},
        "clarification": {"true_positive": tp, "false_positive": fp, "false_negative": fn},
        "abstention": {
            "correct": abstention_correct,
            "total": len(records),
            "predicted": abstention_predicted,
            "required": abstention_required,
        },
        "schema_failures": {"count": failures, "total": len(records)},
        "latency_ms": {
            "measured_examples": len(latencies),
            "median": median(latencies) if latencies else None,
            "p95_nearest_rank": latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)]
            if latencies
            else None,
        },
        "cost": {
            "known_microusd": known_cost,
            "unknown_examples": unknown_cost,
            "known_examples": len(records) - unknown_cost,
        },
    }
