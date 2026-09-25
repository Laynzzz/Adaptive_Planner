from evals.score.metrics import score


def test_exact_denominators_missing_unknown_and_invented_fields():
    records = [
        {
            "reference": {
                "fields": {
                    "tasks.task_1.remaining_minutes": {"value": 60, "label": "explicit"},
                    "tasks.task_1.deadline": {"value": None, "label": "unknown"},
                    "tasks.task_1.predecessor_keys": {"value": [], "label": "explicit"},
                    "tasks.task_1.title": {"value": "Study", "label": "explicit"},
                },
                "constraints": [],
                "required_clarifications": ["tasks.task_1.deadline"],
                "abstained": False,
            },
            "prediction": {
                "fields": {
                    "tasks.task_1.remaining_minutes": {"value": 60, "label": "explicit"},
                    "tasks.task_1.deadline": {"value": "2026-09-30", "label": "explicit"},
                    "tasks.task_2.title": {"value": "Invented", "label": "explicit"},
                },
                "constraints": [],
                "required_clarifications": [],
                "abstained": False,
            },
            "schema_valid": True,
            "latency_ms": 10,
            "cost_microusd": None,
        }
    ]
    result = score(records)
    assert result["critical_fields"]["correct"] == 1
    assert result["critical_fields"]["total"] == 3
    assert result["all_fields"] == {"correct": 1, "total": 4, "missing": 2}
    assert result["invented_fields"] == {"count": 2, "predicted_nonnull_fields": 3}
    assert result["clarification"] == {"true_positive": 0, "false_positive": 0, "false_negative": 1}
    assert result["full_proposals"] == {"correct": 0, "total": 1}
    assert result["cost"]["unknown_examples"] == 1


def test_schema_failure_remains_in_accuracy_denominator():
    result = score(
        [
            {
                "reference": {
                    "fields": {
                        "tasks.task_1.remaining_minutes": {"value": 30, "label": "explicit"}
                    },
                    "constraints": [],
                    "required_clarifications": [],
                    "abstained": False,
                },
                "prediction": None,
                "schema_valid": False,
                "latency_ms": 5,
                "cost_microusd": 0,
            }
        ]
    )
    assert result["critical_fields"]["total"] == 1
    assert result["critical_fields"]["correct"] == 0
    assert result["schema_failures"] == {"count": 1, "total": 1}
    assert result["full_proposals"]["correct"] == 0


def test_frozen_splits_hashes_and_reference_invariants():
    from evals.data.check import load_frozen

    manifest, splits = load_frozen()
    assert [len(splits[name]) for name in ("dev", "validation", "test")] == [60, 30, 30]
    assert len({row["family"] for rows in splits.values() for row in rows}) == 40
    assert manifest["annotation_provenance"]["independent_human_review"] == "PENDING"


def test_correct_unknown_is_a_true_match_and_extra_clarification_is_false_positive():
    reference = {
        "fields": {"tasks.task_1.deadline": {"value": None, "label": "unknown"}},
        "constraints": [{"kind": "SOFT_AVOID", "weekday": 4}],
        "required_clarifications": ["tasks.task_1.deadline"],
        "abstained": False,
    }
    prediction = {
        **reference,
        "required_clarifications": ["tasks.task_1.deadline", "unneeded"],
        "constraints": [{"kind": "HARD_UNAVAILABLE", "weekday": 4}],
    }
    result = score(
        [
            {
                "reference": reference,
                "prediction": prediction,
                "schema_valid": True,
                "latency_ms": 0,
                "cost_microusd": 0,
            }
        ]
    )
    assert result["critical_fields"]["correct"] == result["critical_fields"]["total"] == 1
    assert result["invented_fields"]["count"] == 0
    assert result["clarification"] == {"true_positive": 1, "false_positive": 1, "false_negative": 0}
    assert result["hard_soft"] == {"correct": 0, "total": 1, "unmatched_predicted_constraints": 1}
    assert result["full_proposals"]["correct"] == 0
