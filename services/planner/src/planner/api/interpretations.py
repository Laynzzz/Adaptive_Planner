"""Interpretations enqueue work; only reviewed acceptance changes planning inputs."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.ai.accept import accept_in_transaction
from planner.ai.schema import ExtractionDraft
from planner.api.auth import Principal, require_mutation, require_session
from planner.api.errors import APIError
from planner.api.plans import _command
from planner.db.ai_models import InterpretationRecord
from planner.db.models import Identity
from planner.domain.commands import execute_command
from planner.domain.contracts import Contract

router = APIRouter(prefix="/api/v1", tags=["interpretations"])


class InterpretCommand(Contract):
    expected_revision: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=8000)
    mode: Literal["mock", "openai"] = "mock"


class InterpretationView(Contract):
    id: UUID
    state: Literal["QUEUED", "RUNNING", "READY", "FAILED", "ACCEPTED"]
    planning_revision: int
    source_text: str
    reference_now: datetime
    timezone: str
    proposal: ExtractionDraft | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = {}


class InterpretationQueued(Contract):
    id: UUID
    state: str
    planning_revision: int


class AcceptCommand(Contract):
    expected_revision: int = Field(ge=0)
    selected_task_keys: tuple[str, ...] = Field(default=(), max_length=20)
    selected_constraint_keys: tuple[str, ...] | None = Field(default=None, max_length=20)
    confirmed_fields: tuple[str, ...] = ()
    overrides: dict[str, Any] = {}


class AcceptedView(Contract):
    interpretation_id: UUID
    task_ids: tuple[UUID, ...]
    weekday_rule_ids: tuple[UUID, ...] = ()
    revision: int


@router.post("/interpretations", response_model=InterpretationQueued, status_code=202)
def enqueue(
    body: InterpretCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    def mutate(db, state, now):
        active = db.scalar(
            select(InterpretationRecord.id).where(
                InterpretationRecord.owner_id == principal.owner_id,
                InterpretationRecord.state.in_(["QUEUED", "RUNNING"]),
            )
        )
        if active:
            raise APIError(
                "INTERPRETATION_ACTIVE",
                409,
                "An interpretation is already running.",
                retryable=True,
            )
        identity = db.get(Identity, principal.owner_id)
        row = InterpretationRecord(
            owner_id=principal.owner_id,
            source_text=body.text,
            planning_revision=state.revision,
            reference_now=now,
            timezone=identity.timezone,
            mode=body.mode,
            state="QUEUED",
            created_at=now,
        )
        db.add(row)
        db.flush()
        return {"id": str(row.id), "state": "QUEUED", "planning_revision": state.revision}

    return _command(
        request, principal, "interpretations.create", body.model_dump(mode="json"), mutate, 202
    )


@router.get("/interpretations/{interpretation_id}", response_model=InterpretationView)
def get_interpretation(
    interpretation_id: UUID, request: Request, principal: Principal = Depends(require_session)
):
    with Session(request.app.state.engine) as db:
        row = db.scalar(
            select(InterpretationRecord).where(
                InterpretationRecord.id == interpretation_id,
                InterpretationRecord.owner_id == principal.owner_id,
            )
        )
        if row is None:
            raise APIError("NOT_FOUND", 404, "Interpretation not found.")
        return InterpretationView(
            id=row.id,
            state=row.state,
            planning_revision=row.planning_revision,
            source_text=row.source_text,
            reference_now=row.reference_now,
            timezone=row.timezone,
            proposal=ExtractionDraft.model_validate(row.proposal) if row.proposal else None,
            error_code=row.error_code,
            metadata=row.metadata_json,
        )


@router.post("/interpretations/{interpretation_id}/accept", response_model=AcceptedView)
def accept(
    interpretation_id: UUID,
    body: AcceptCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        row = db.scalar(
            select(InterpretationRecord).where(
                InterpretationRecord.id == interpretation_id,
                InterpretationRecord.owner_id == principal.owner_id,
            )
        )
        if row is not None and row.planning_revision != body.expected_revision:
            raise APIError(
                "STALE_INTERPRETATION",
                409,
                "Inputs changed after this interpretation; create a new review.",
            )
        return accept_in_transaction(
            db,
            principal.owner_id,
            interpretation_id,
            body.selected_task_keys,
            body.confirmed_fields,
            body.overrides,
            now=request.app.state.clock(),
            selected_constraint_keys=body.selected_constraint_keys,
        )

    response, status = execute_command(
        request.app.state.engine,
        principal.owner_id,
        "interpretations.accept:" + str(interpretation_id),
        request.headers.get("Idempotency-Key"),
        body.model_dump(mode="json"),
        request.app.state.clock,
        mutate,
    )
    return JSONResponse(response, status_code=status)
