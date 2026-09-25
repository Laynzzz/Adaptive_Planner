"""Calendar identity and manual-change decisions shared by sync and publication."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import select

from planner.calendar.provider import CalendarEvent
from planner.db.calendar_models import CalendarConflict

APP_MARKER = "adaptive-planner-v1"


def event_id(owner_id: UUID, calendar_id: str, block_id: UUID) -> str:
    # Hexadecimal is a subset of Google's lowercase base32hex event ID alphabet.
    return hashlib.sha256(f"{owner_id}/{calendar_id}/{block_id}".encode()).hexdigest()


def owned(payload: dict, owner_id: UUID, block_id: UUID) -> bool:
    marker = payload.get("extendedProperties", {}).get("private", {})
    return (
        marker.get("app") == APP_MARKER
        and marker.get("owner") == str(owner_id)
        and marker.get("block") == str(block_id)
    )


def canonical(payload: dict | None) -> dict | None:
    if payload is None:
        return None
    interval = CalendarEvent(id=payload.get("id", ""), payload=payload).interval()
    return {
        "id": payload.get("id"),
        "summary": payload.get("summary", ""),
        "description": payload.get("description", ""),
        "location": payload.get("location", ""),
        "interval": [v.isoformat() for v in interval] if interval else None,
        "status": payload.get("status", "confirmed"),
        "transparency": payload.get("transparency", "opaque"),
        "marker": payload.get("extendedProperties", {}).get("private", {}),
    }


def payload_for(owner_id, calendar_id, block, title):
    return {
        "id": event_id(owner_id, calendar_id, block.id),
        "summary": title,
        "status": "confirmed",
        "start": {"dateTime": block.start.isoformat()},
        "end": {"dateTime": block.end.isoformat()},
        "extendedProperties": {
            "private": {"app": APP_MARKER, "owner": str(owner_id), "block": str(block.id)}
        },
    }


def conflict(db, mapping, reason, remote, now):
    existing = db.scalar(
        select(CalendarConflict).where(
            CalendarConflict.owner_id == mapping.owner_id,
            CalendarConflict.block_id == mapping.block_id,
            CalendarConflict.state == "OPEN",
        )
    )
    if existing is None:
        db.add(
            CalendarConflict(
                owner_id=mapping.owner_id,
                block_id=mapping.block_id,
                reason=reason,
                remote_payload=remote,
                created_at=now,
            )
        )
    else:
        existing.reason, existing.remote_payload = reason, remote
    mapping.state = "CONFLICT"
    if remote and owned(remote, mapping.owner_id, mapping.block_id):
        interval = CalendarEvent(id=mapping.event_id, payload=remote).interval()
        if interval:
            mapping.commitment = {"start": interval[0].isoformat(), "end": interval[1].isoformat()}


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
