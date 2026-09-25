"""Authenticated commands; every accepted input edit is one revision transaction."""

import base64
import json
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.orm import Session

from planner.api.auth import Principal, require_mutation, require_session
from planner.api.errors import APIError
from planner.api.schemas import (
    AvailabilityCommand,
    AvailabilityResponse,
    DependencyCommand,
    FixedEventCreate,
    FixedEventPage,
    FixedEventPatch,
    FixedEventResponse,
    RevisionCommand,
    RevisionResponse,
    TaskCreate,
    TaskFields,
    TaskPage,
    TaskPatch,
    TaskResponse,
)
from planner.db.models import (
    Availability,
    DependencyEdge,
    FixedEvent,
    Identity,
    PlanningState,
    Task,
)
from planner.db.queries import task_page_data
from planner.db.repositories import owned_task, task_data
from planner.domain.commands import execute_command
from planner.domain.time_rules import normalize_time_inputs, resolve_local_time

router = APIRouter(prefix="/api/v1")


def transact(request, principal, payload, mutate, status=200):
    try:
        result, code = execute_command(
            request.app.state.engine,
            principal.owner_id,
            request.method + " " + request.url.path,
            request.headers.get("Idempotency-Key"),
            payload,
            request.app.state.clock,
            mutate,
            status,
        )
    except (ValueError, ValidationError, ZoneInfoNotFoundError):
        raise APIError(
            "INVALID_INPUT", 422, "Check time values, duration, and block settings."
        ) from None
    return JSONResponse(result, status_code=code)


def validate_task(db, owner_id, data, clock):
    from planner.domain.weekday_rules import assert_deadline_allowed
    TaskFields.model_validate(data)
    identity = db.get(Identity, owner_id)
    normalize_time_inputs(
        {
            "owner_id": str(owner_id),
            "timezone": identity.timezone,
            "tasks": [{"id": str(uuid4()), **data}],
        },
        clock(),
    )
    assert_deadline_allowed(db, owner_id, data)


def apply_task_data(task, data):
    task.title = data["title"]
    task.remaining_minutes = data["remaining_minutes"]
    task.priority = data["priority"]
    task.details = {
        key: value
        for key, value in data.items()
        if key not in ("title", "remaining_minutes", "priority")
    }


@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    body: TaskCreate, request: Request, principal: Principal = Depends(require_mutation)
):
    payload = body.model_dump(mode="json")

    def mutate(db):
        count = db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.owner_id == principal.owner_id, Task.state.notin_(["DONE", "CANCELLED"]))
        )
        if count >= 200:
            raise APIError("ACTIVE_TASK_LIMIT", 422, "At most 200 active tasks are supported.")
        data = {key: value for key, value in payload.items() if key != "expected_revision"}
        validate_task(db, principal.owner_id, data, request.app.state.clock)
        task = Task(owner_id=principal.owner_id, state="TODO")
        apply_task_data(task, data)
        db.add(task)
        db.flush()
        return task_data(db, task)

    return transact(request, principal, payload, mutate, 201)


@router.get("/tasks", response_model=TaskPage)
def list_tasks(
    request: Request,
    state: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_session),
):
    if limit < 1 or limit > 100 or state not in (None, "TODO", "IN_PROGRESS", "DONE", "CANCELLED"):
        raise APIError("INVALID_INPUT", 422, "Invalid page limit or state filter.")
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        query = select(Task).where(Task.owner_id == principal.owner_id)
        if state:
            query = query.where(Task.state == state)
        if cursor:
            try:
                if len(cursor) > 2048:
                    raise ValueError()
                values = json.loads(base64.urlsafe_b64decode(cursor))
                if values["owner"] != str(principal.owner_id) or values["state"] != state:
                    raise ValueError()
                upper = (datetime.fromisoformat(values["upper"][0]), UUID(values["upper"][1]))
                after = (datetime.fromisoformat(values["after"][0]), UUID(values["after"][1]))
            except (ValueError, KeyError, TypeError, IndexError):
                raise APIError("CURSOR_INVALID", 400, "Cursor does not match this scan.") from None
            query = query.where(tuple_(Task.created_at, Task.id) > after)
        else:
            last = db.scalar(query.order_by(Task.created_at.desc(), Task.id.desc()).limit(1))
            upper = (last.created_at, last.id) if last else None
        if upper:
            query = query.where(tuple_(Task.created_at, Task.id) <= upper)
        tasks = db.scalars(query.order_by(Task.created_at, Task.id).limit(limit + 1)).all()
        more = len(tasks) > limit
        tasks = tasks[:limit]
        revision = db.get(PlanningState, principal.owner_id).revision
        next_cursor = None
        if more:
            last = tasks[-1]
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "owner": str(principal.owner_id),
                        "state": state,
                        "upper": [upper[0].isoformat(), str(upper[1])],
                        "after": [last.created_at.isoformat(), str(last.id)],
                    }
                ).encode()
            ).decode()
        return {
            "items": task_page_data(db, tasks, revision),
            "next_cursor": next_cursor,
            "revision": revision,
        }


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: UUID, request: Request, principal: Principal = Depends(require_session)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        return task_data(
            db,
            owned_task(db, principal.owner_id, task_id),
            db.get(PlanningState, principal.owner_id).revision,
        )


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: UUID,
    body: TaskPatch,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    payload = body.model_dump(mode="json", exclude_unset=True)

    def mutate(db):
        task = owned_task(db, principal.owner_id, task_id)
        if task.state in ("DONE", "CANCELLED"):
            raise APIError("TASK_INACTIVE", 409, "This task is no longer active.")
        data = {
            **task.details,
            "title": task.title,
            "remaining_minutes": task.remaining_minutes,
            "priority": task.priority,
        }
        data.update({key: value for key, value in payload.items() if key != "expected_revision"})
        validate_task(db, principal.owner_id, data, request.app.state.clock)
        apply_task_data(task, data)
        db.flush()
        return task_data(db, task)

    return transact(request, principal, payload, mutate)


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(
    task_id: UUID,
    body: RevisionCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        task = owned_task(db, principal.owner_id, task_id)
        task.state = "CANCELLED"
        return task_data(db, task)

    return transact(request, principal, body.model_dump(mode="json"), mutate)


@router.post("/tasks/{task_id}/dependencies", response_model=RevisionResponse)
def add_dependency(
    task_id: UUID,
    body: DependencyCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        predecessor = owned_task(db, principal.owner_id, body.predecessor_id)
        owned_task(db, principal.owner_id, task_id)
        if predecessor.state == "CANCELLED":
            raise APIError("CANCELLED_PREDECESSOR", 422, "Resolve the cancelled predecessor.")
        edges = db.scalars(
            select(DependencyEdge).where(DependencyEdge.owner_id == principal.owner_id)
        ).all()
        graph = {}
        for edge in edges:
            graph.setdefault(edge.predecessor_id, set()).add(edge.successor_id)
        pending, seen = [task_id], set()
        while pending:
            node = pending.pop()
            if node == body.predecessor_id:
                raise APIError("DEPENDENCY_CYCLE", 422, "This dependency creates a cycle.")
            if node not in seen:
                seen.add(node)
                pending.extend(graph.get(node, ()))
        if task_id not in graph.get(body.predecessor_id, ()):
            db.add(
                DependencyEdge(
                    owner_id=principal.owner_id,
                    predecessor_id=body.predecessor_id,
                    successor_id=task_id,
                )
            )
        return {}

    return transact(request, principal, body.model_dump(mode="json"), mutate)


@router.delete("/tasks/{task_id}/dependencies", response_model=RevisionResponse)
def remove_dependency(
    task_id: UUID,
    body: DependencyCommand,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    def mutate(db):
        owned_task(db, principal.owner_id, task_id)
        owned_task(db, principal.owner_id, body.predecessor_id)
        db.execute(
            delete(DependencyEdge).where(
                DependencyEdge.owner_id == principal.owner_id,
                DependencyEdge.successor_id == task_id,
                DependencyEdge.predecessor_id == body.predecessor_id,
            )
        )
        return {}

    return transact(request, principal, body.model_dump(mode="json"), mutate)


def validate_intervals(intervals, timezone):
    def instant(value):
        if value is None:
            raise ValueError("An interval endpoint is required")
        if isinstance(value, dict):
            return resolve_local_time(
                datetime.fromisoformat(value["local"]),
                value.get("timezone", timezone),
                value.get("fold"),
            )
        return resolve_local_time(datetime.fromisoformat(value), timezone)

    for interval in intervals:
        if instant(interval["start"]) >= instant(interval["end"]):
            raise ValueError("Interval must be nonempty")


@router.get("/availability", response_model=AvailabilityResponse)
def get_availability(request: Request, principal: Principal = Depends(require_session)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        row = db.get(Availability, principal.owner_id)
        return {
            "windows": row.windows if row else [],
            "timezone": db.get(Identity, principal.owner_id).timezone,
            "revision": db.get(PlanningState, principal.owner_id).revision,
        }


@router.put("/availability", response_model=AvailabilityResponse)
def set_availability(
    body: AvailabilityCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    payload = body.model_dump(mode="json")

    def mutate(db):
        timezone = db.get(Identity, principal.owner_id).timezone
        validate_intervals(payload["windows"], timezone)
        row = db.get(Availability, principal.owner_id)
        if row is None:
            row = Availability(owner_id=principal.owner_id)
            db.add(row)
        row.windows = payload["windows"]
        return {"windows": row.windows, "timezone": timezone}

    return transact(request, principal, payload, mutate)


@router.get("/fixed-events", response_model=FixedEventPage)
def list_events(request: Request, principal: Principal = Depends(require_session)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        revision = db.get(PlanningState, principal.owner_id).revision
        events = db.scalars(
            select(FixedEvent).where(FixedEvent.owner_id == principal.owner_id)
        ).all()
        return {
            "items": [
                {"id": str(e.id), "title": e.title, **e.details, "revision": revision}
                for e in events
            ],
            "revision": revision,
        }


@router.post("/fixed-events", response_model=FixedEventResponse, status_code=201)
def create_event(
    body: FixedEventCreate, request: Request, principal: Principal = Depends(require_mutation)
):
    payload = body.model_dump(mode="json")

    def mutate(db):
        details = {key: payload[key] for key in ("start", "end")}
        validate_intervals([details], db.get(Identity, principal.owner_id).timezone)
        event = FixedEvent(owner_id=principal.owner_id, title=body.title, details=details)
        db.add(event)
        db.flush()
        return {"id": str(event.id), "title": event.title, **details}

    return transact(request, principal, payload, mutate, 201)


@router.patch("/fixed-events/{event_id}", response_model=FixedEventResponse)
def patch_event(
    event_id: UUID,
    body: FixedEventPatch,
    request: Request,
    principal: Principal = Depends(require_mutation),
):
    payload = body.model_dump(mode="json", exclude_unset=True)

    def mutate(db):
        event = db.scalar(
            select(FixedEvent).where(
                FixedEvent.id == event_id, FixedEvent.owner_id == principal.owner_id
            )
        )
        if event is None:
            raise APIError("NOT_FOUND", 404, "Resource not found.")
        details = {**event.details, **{k: v for k, v in payload.items() if k in ("start", "end")}}
        validate_intervals([details], db.get(Identity, principal.owner_id).timezone)
        if "title" in payload:
            if not payload["title"]:
                raise ValueError("Title required")
            event.title = payload["title"]
        event.details = details
        return {"id": str(event.id), "title": event.title, **details}

    return transact(request, principal, payload, mutate)
