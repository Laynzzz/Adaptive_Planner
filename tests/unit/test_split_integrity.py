from benchmarks.generate import generate_scenario
from planner.domain.contracts import Candidate, InputSnapshot
from planner.solver.validator import validate_candidate


def test_generator_supplies_real_validated_witness_and_deterministic_hash():
    row = generate_scenario(1)
    snapshot = InputSnapshot.model_validate(row["snapshot"])
    witness = Candidate.model_validate(row["witness"])
    assert not validate_candidate(snapshot, witness)
    assert row == generate_scenario(1)


def test_related_scenarios_never_cross_splits():
    rows = [generate_scenario(i) for i in range(1000)]
    assert [
        sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")
    ] == [600, 200, 200]
    assert len({row["group_id"] for row in rows}) == 1000
    groups = {
        split: {r["group_id"] for r in rows if r["split"] == split}
        for split in ("train", "validation", "test")
    }
    assert groups["train"].isdisjoint(groups["validation"] | groups["test"])
    assert groups["validation"].isdisjoint(groups["test"])
