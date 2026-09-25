"""Explicit timezone preview and revision-bound confirmation."""

from typing import Literal
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy.orm import Session

from planner.api.auth import Principal, require_mutation, require_session
from planner.api.errors import APIError
from planner.api.routes import transact
from planner.api.schemas import RevisionCommand, RevisionResponse, Schema
from planner.domain.timezone_change import apply_timezone, preview_timezone

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class DateDeadlineChange(Schema):
    task_id: str
    title: str
    date: str
    old_bound: str
    new_bound: str


class TimezonePreview(Schema):
    old_timezone: str
    timezone: str
    revision: int
    date_deadlines: list[DateDeadlineChange]
    preserved_fixed_events: int
    preserved_available_windows: int
    weekly_rules_follow_new_timezone: bool
    preview_hash: str


class TimezoneCommand(RevisionCommand):
    timezone: str = Field(min_length=1, max_length=100)
    preview_hash: str = Field(min_length=64, max_length=64)
    confirmed: Literal[True]


class TimezoneSaved(RevisionResponse):
    timezone: str


@router.get("/timezone-preview", response_model=TimezonePreview)
def preview(
    request: Request,
    timezone: str = Query(min_length=1, max_length=100),
    principal: Principal = Depends(require_session),
):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        try:
            return preview_timezone(db, principal.owner_id, timezone)[0]
        except (ValueError, ZoneInfoNotFoundError):
            raise APIError(
                "INVALID_TIMEZONE",
                422,
                "Choose a valid IANA timezone with resolvable date boundaries.",
            ) from None


@router.put("/timezone", response_model=TimezoneSaved)
def change(
    body: TimezoneCommand, request: Request, principal: Principal = Depends(require_mutation)
):
    def mutate(db):
        reviewed, updates = preview_timezone(db, principal.owner_id, body.timezone)
        if reviewed["preview_hash"] != body.preview_hash:
            raise APIError(
                "STALE_TIMEZONE_PREVIEW", 409, "Inputs changed. Preview the timezone change again."
            )
        apply_timezone(db, principal.owner_id, body.timezone, updates, request.app.state.clock())
        return {"timezone": body.timezone}

    return transact(request, principal, body.model_dump(mode="json"), mutate)
