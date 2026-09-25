"""Manual weekday rules use the same reviewed transactional path as extraction."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.api.auth import Principal, require_mutation, require_session
from planner.api.errors import APIError
from planner.api.routes import transact
from planner.api.schemas import RevisionCommand, RevisionResponse, Schema
from planner.db.models import Identity, PlanningState
from planner.db.weekday_models import WeekdayRule
from planner.domain.weekday_rules import accept_weekday_rule, rules_for

router = APIRouter(prefix="/api/v1", tags=["weekday-rules"])


class RuleFields(Schema):
    kind: Literal["SOFT_AVOID", "HARD_UNAVAILABLE", "HARD_NO_DEADLINE"]
    weekday: int = Field(ge=0, le=6, strict=True)


class RuleCommand(RuleFields, RevisionCommand):
    pass


class RuleView(RuleFields):
    id: UUID


class CreatedRule(RuleView, RevisionResponse):
    pass


class RuleList(Schema):
    items: list[RuleView]
    timezone: str
    revision: int


@router.get("/weekday-rules", response_model=RuleList)
def list_rules(request: Request, principal: Principal = Depends(require_session)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        return {
            "items": [
                {"id": r.id, "kind": r.kind, "weekday": r.weekday}
                for r in rules_for(db, principal.owner_id)
            ],
            "timezone": db.get(Identity, principal.owner_id).timezone,
            "revision": db.get(PlanningState, principal.owner_id).revision,
        }


@router.post("/weekday-rules", response_model=CreatedRule, status_code=201)
def create_rule(
    body: RuleCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    def mutate(db):
        rule_id = accept_weekday_rule(
            db, principal.owner_id, body.kind, body.weekday, request.app.state.clock()
        )
        return {"id": str(rule_id), "kind": body.kind, "weekday": body.weekday}

    return transact(request, principal, body.model_dump(mode="json"), mutate, 201)


@router.delete("/weekday-rules/{rule_id}", response_model=RevisionResponse)
def delete_rule(
    rule_id: UUID,
    body: RevisionCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        row = db.scalar(
            select(WeekdayRule).where(
                WeekdayRule.id == rule_id, WeekdayRule.owner_id == principal.owner_id
            )
        )
        if row is None:
            raise APIError("NOT_FOUND", 404, "Weekday rule not found.")
        db.delete(row)
        return {}

    return transact(request, principal, body.model_dump(mode="json"), mutate)
