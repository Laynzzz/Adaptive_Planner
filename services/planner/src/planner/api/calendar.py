"""Authenticated exports and explicit calendar commands; remote work is queued."""

import hashlib
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from planner.api.auth import Principal, require_mutation, require_session
from planner.api.errors import APIError
from planner.api.plans import RevisionCommand, _command
from planner.calendar.ics import export_ics
from planner.calendar.oauth import CalendarConfig, begin_oauth, exchange_callback
from planner.db.calendar_models import (
    BlockEventMapping,
    CalendarConflict,
    CalendarConnection,
    CalendarOAuthFlow,
    CalendarWriteOperation,
)
from planner.db.job_models import ProposalRecord
from planner.db.models import AuditEvent, PlanningState, Task
from planner.domain.commands import execute_command
from planner.domain.contracts import Candidate, Contract
from planner.jobs.coalescing import enqueue_in_transaction

router = APIRouter(prefix="/api/v1", tags=["calendar"])


class ConnectCalendar(RevisionCommand):
    provider: Literal["MOCK", "GOOGLE"]
    calendar_id: str = Field(min_length=1, max_length=500)
    dedicated_synthetic_confirmed: bool


class DisconnectCalendar(RevisionCommand):
    keep_remote_events: bool


class ResolveCalendarConflict(RevisionCommand):
    action: Literal["RESTORE", "ACCEPT_DELETION", "REMOVE_COMMITMENT", "DISCONNECT"]


class CalendarCommandView(Contract):
    state: str
    revision: int
    authorization_url: str | None = None


class CalendarConflictView(Contract):
    id: UUID
    block_id: UUID
    reason: str
    remote_start: datetime | None = None
    remote_end: datetime | None = None


class CalendarStatusView(Contract):
    state: str
    provider: str | None = None
    calendar_id: str | None = None
    revision: int
    live_configured: bool
    mock_available: bool = True
    last_sync_at: datetime | None = None
    error_code: str | None = None
    sync_pending: bool = False
    publish_pending: bool = False
    published_count: int = 0
    pending_count: int = 0
    conflicts: tuple[CalendarConflictView, ...] = ()


def _config(request):
    return getattr(request.app.state, "calendar_config", CalendarConfig())


def _input_command(request, principal, name, body, mutate):
    return execute_command(
        request.app.state.engine,
        principal.owner_id,
        name,
        request.headers.get("Idempotency-Key", ""),
        body.model_dump(mode="json"),
        request.app.state.clock,
        mutate,
    )[0]


@router.get("/exports/calendar.ics")
def calendar_export(request: Request, principal: Principal = Depends(require_session)):
    with Session(request.app.state.engine) as db:
        state = db.get(PlanningState, principal.owner_id)
        proposal = (
            db.get(ProposalRecord, state.active_proposal_id) if state.active_proposal_id else None
        )
        if not proposal or proposal.owner_id != principal.owner_id:
            raise APIError("ACTIVE_PLAN_REQUIRED", 409, "Activate a plan before exporting it.")
        titles = {
            t.id: t.title
            for t in db.scalars(select(Task).where(Task.owner_id == principal.owner_id))
        }
        content = export_ics(
            Candidate.model_validate(proposal.candidate),
            titles,
            generated_at=request.app.state.clock(),
        )
    return Response(
        content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="adaptive-planner.ics"'},
    )


@router.post("/calendar/connect", response_model=CalendarCommandView)
def connect_calendar(
    body: ConnectCalendar, request: Request, principal: Principal = Depends(require_mutation)
):
    if not body.dedicated_synthetic_confirmed:
        raise APIError(
            "SYNTHETIC_CALENDAR_REQUIRED",
            422,
            "Select a dedicated synthetic calendar and confirm it.",
        )

    def mutate(db):
        connection = db.get(CalendarConnection, principal.owner_id)
        if connection and connection.state not in ("DISCONNECTED", "NEEDS_REAUTH", "AUTHORIZING"):
            raise APIError(
                "CALENDAR_ALREADY_CONNECTED", 409, "Disconnect the current calendar first."
            )
        if connection and (
            connection.calendar_id != body.calendar_id or connection.provider != body.provider
        ):
            raise APIError(
                "CALENDAR_IDENTITY_CONFLICT",
                409,
                "This workspace retains mappings for its original dedicated calendar.",
            )
        if not connection:
            connection = CalendarConnection(
                owner_id=principal.owner_id, provider=body.provider, calendar_id=body.calendar_id
            )
            db.add(connection)
            db.flush()
        connection.state = "CONNECTED" if body.provider == "MOCK" else "AUTHORIZING"
        connection.generation += 1
        connection.retry_at = connection.last_error = None
        connection.sync_request = uuid4() if body.provider == "MOCK" else None
        connection.publish_request = uuid4() if body.provider == "MOCK" else None
        response = {"state": connection.state}
        if body.provider == "GOOGLE":
            response["authorization_url"] = begin_oauth(
                db,
                principal.owner_id,
                principal.token_hash,
                body.calendar_id,
                _config(request),
                request.app.state.clock(),
            )
        return response

    return _input_command(request, principal, "calendar.connect", body, mutate)


@router.get("/calendar/callback")
def calendar_callback(
    request: Request, state: str, code: str, principal: Principal = Depends(require_session)
):
    calendar_id, encrypted = exchange_callback(
        request.app.state.engine,
        principal.owner_id,
        principal.token_hash,
        state,
        code,
        _config(request),
        request.app.state.clock,
        client=getattr(request.app.state, "calendar_oauth_client", None),
    )
    with Session(request.app.state.engine) as db, db.begin():
        planning = db.scalar(
            select(PlanningState)
            .where(PlanningState.owner_id == principal.owner_id)
            .with_for_update()
        )
        connection = db.scalar(
            select(CalendarConnection)
            .where(CalendarConnection.owner_id == principal.owner_id)
            .with_for_update()
        )
        if (
            connection.state != "AUTHORIZING"
            or connection.calendar_id != calendar_id
            or connection.oauth_state_hash != hashlib.sha256(state.encode()).hexdigest()
        ):
            raise APIError(
                "CALENDAR_OAUTH_SUPERSEDED",
                409,
                "Calendar authorization was cancelled or replaced.",
            )
        connection.state, connection.encrypted_refresh_token = "CONNECTED", encrypted
        connection.sync_request, connection.publish_request = uuid4(), uuid4()
        connection.oauth_state_hash = None
        planning.revision += 1
        db.add(
            AuditEvent(
                owner_id=principal.owner_id,
                operation="calendar.callback",
                revision=planning.revision,
            )
        )
        enqueue_in_transaction(db, principal.owner_id, now=request.app.state.clock())
    return RedirectResponse(request.app.state.settings.ui_origin, status_code=302)


@router.post("/calendar/disconnect", response_model=CalendarCommandView)
def disconnect_calendar(
    body: DisconnectCalendar, request: Request, principal: Principal = Depends(require_mutation)
):
    def mutate(db):
        connection = db.get(CalendarConnection, principal.owner_id)
        if not connection:
            raise APIError("CALENDAR_NOT_FOUND", 404, "Calendar connection not found.")
        connection.state, connection.keep_remote_events = "DISCONNECTING", body.keep_remote_events
        connection.sync_request = connection.publish_request = connection.oauth_state_hash = None
        connection.retry_at = None
        connection.generation += 1
        db.execute(
            delete(CalendarOAuthFlow).where(CalendarOAuthFlow.owner_id == principal.owner_id)
        )
        return {"state": "DISCONNECTING"}

    return _input_command(request, principal, "calendar.disconnect", body, mutate)


def _queue(request, principal, body, action):
    def mutate(db, state, now):
        connection = db.get(CalendarConnection, principal.owner_id)
        if not connection or connection.state != "CONNECTED":
            raise APIError(
                "CALENDAR_NOT_CONNECTED", 409, "Connect or reauthorize the calendar first."
            )
        setattr(connection, action + "_request", uuid4())
        connection.retry_at = None
        return {"state": "QUEUED", "revision": state.revision}

    return _command(request, principal, "calendar." + action, body.model_dump(mode="json"), mutate)


@router.post("/calendar/sync", response_model=CalendarCommandView)
def sync_calendar(
    body: RevisionCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    return _queue(request, principal, body, "sync")


@router.post("/calendar/publish", response_model=CalendarCommandView)
def publish_calendar(
    body: RevisionCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    return _queue(request, principal, body, "publish")


@router.get("/calendar/status", response_model=CalendarStatusView)
def calendar_status(request: Request, principal: Principal = Depends(require_session)):
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        planning = db.get(PlanningState, principal.owner_id)
        connection = db.get(CalendarConnection, principal.owner_id)
        fields = dict(
            state=connection.state if connection else "DISCONNECTED",
            revision=planning.revision,
            live_configured=_config(request).configured,
        )
        if connection:
            conflicts = list(
                db.scalars(
                    select(CalendarConflict).where(
                        CalendarConflict.owner_id == principal.owner_id,
                        CalendarConflict.state == "OPEN",
                    )
                )
            )
            operations = list(
                db.scalars(
                    select(CalendarWriteOperation).where(
                        CalendarWriteOperation.owner_id == principal.owner_id,
                        CalendarWriteOperation.proposal_id == planning.active_proposal_id,
                    )
                )
            )
            fields.update(
                provider=connection.provider,
                calendar_id=connection.calendar_id,
                last_sync_at=connection.last_sync_at,
                error_code=connection.last_error,
                sync_pending=connection.sync_request is not None,
                publish_pending=connection.publish_request is not None,
                published_count=sum(x.state == "DONE" for x in operations),
                pending_count=sum(x.state != "DONE" for x in operations),
                conflicts=tuple(
                    CalendarConflictView(id=x.id, block_id=x.block_id, reason=x.reason)
                    for x in conflicts
                ),
            )
        return CalendarStatusView(**fields)


@router.post("/calendar/conflicts/{conflict_id}/resolve", response_model=CalendarCommandView)
def resolve_calendar_conflict(
    conflict_id: UUID,
    body: ResolveCalendarConflict,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        conflict = db.scalar(
            select(CalendarConflict).where(
                CalendarConflict.id == conflict_id,
                CalendarConflict.owner_id == principal.owner_id,
                CalendarConflict.state == "OPEN",
            )
        )
        if not conflict:
            raise APIError("CALENDAR_CONFLICT_NOT_FOUND", 404, "Open calendar conflict not found.")
        mapping = db.get(BlockEventMapping, (principal.owner_id, conflict.block_id))
        connection = db.get(CalendarConnection, principal.owner_id)
        if body.action == "DISCONNECT":
            connection.state, connection.keep_remote_events = "DISCONNECTING", True
        elif body.action == "RESTORE":
            if conflict.reason == "OWNERSHIP_MISMATCH":
                raise APIError(
                    "OWNERSHIP_CONFLICT",
                    409,
                    "Disconnect publication; an event owned elsewhere cannot be overwritten.",
                )
            mapping.state, mapping.commitment = "PENDING", None
            # Explicit consent establishes the reviewed remote baseline for a conditional restore.
            mapping.published_payload = (
                conflict.remote_payload if conflict.reason != "MANUAL_DELETION" else None
            )
            if conflict.remote_payload:
                mapping.etag = conflict.remote_payload.get("etag", "")
            for op in db.scalars(
                select(CalendarWriteOperation).where(
                    CalendarWriteOperation.owner_id == principal.owner_id,
                    CalendarWriteOperation.block_id == mapping.block_id,
                )
            ):
                op.state = "PENDING"
            connection.publish_request = uuid4()
        else:
            if body.action == "ACCEPT_DELETION" and conflict.reason != "MANUAL_DELETION":
                raise APIError(
                    "RESOLUTION_INVALID", 422, "Accept deletion applies to deleted events."
                )
            mapping.state, mapping.commitment = "IGNORED", None
        conflict.state = "RESOLVED"
        connection.retry_at = None
        return {"state": body.action}

    return _input_command(request, principal, "calendar.resolve." + str(conflict_id), body, mutate)
