"""Atomic, conservative accounting before any paid network attempt."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from planner.ai.provider import ProviderError, maximum_charge
from planner.db.ai_models import AISpendBudget, AISpendReservation, InterpretationRecord


def reserve(engine, claim, config) -> int:
    amount = maximum_charge(claim.context, config)
    with Session(engine) as db, db.begin():
        record = db.get(InterpretationRecord, claim.id, with_for_update=True)
        if (
            record is None
            or record.owner_id != claim.owner_id
            or record.state != "RUNNING"
            or record.fencing_token != claim.token
            or record.lease_until
            <= datetime.now(UTC) + timedelta(seconds=config.provider_timeout_seconds)
        ):
            raise ProviderError("CLAIM_LOST")
        db.execute(
            insert(AISpendBudget)
            .values(id="openai", reserved_microusd=0, spent_microusd=0)
            .on_conflict_do_nothing()
        )
        budget = db.get(AISpendBudget, "openai", with_for_update=True)
        if db.get(AISpendReservation, claim.id):
            raise ProviderError("SPEND_ALREADY_RESERVED")
        if budget.spent_microusd + budget.reserved_microusd + amount > config.budget_microusd:
            raise ProviderError("SPEND_LIMIT")
        budget.reserved_microusd += amount
        db.add(
            AISpendReservation(
                interpretation_id=claim.id,
                owner_id=claim.owner_id,
                amount_microusd=amount,
                actual_cost_known=False,
            )
        )
    return amount


def settle(db, interpretation_id, result, config):
    reservation = db.get(AISpendReservation, interpretation_id, with_for_update=True)
    if not reservation or reservation.settled_microusd is not None:
        return None
    known = (
        result is not None
        and result.attempts == 1
        and result.input_tokens is not None
        and result.output_tokens is not None
    )
    if known:
        cost = (
            result.input_tokens * config.input_rate_microusd_per_million
            + result.output_tokens * config.output_rate_microusd_per_million
            + 999999
        ) // 1000000
    else:
        cost = reservation.amount_microusd
    budget = db.get(AISpendBudget, "openai", with_for_update=True)
    budget.reserved_microusd -= reservation.amount_microusd
    budget.spent_microusd += cost
    reservation.settled_microusd = cost
    reservation.actual_cost_known = known
    return cost if known else None
