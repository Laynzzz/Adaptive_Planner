"""Typed provider boundary; errors preserve recovery meaning without provider text."""

from datetime import UTC, date, datetime, time
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

ErrorKind = Literal[
    "RETRYABLE",
    "AMBIGUOUS_WRITE",
    "AUTHENTICATION_REQUIRED",
    "PERMANENT_VALIDATION",
    "CONFLICT",
    "INVALID_SYNC_TOKEN",
    "NOT_FOUND",
]


class ProviderError(Exception):
    def __init__(self, kind: ErrorKind):
        self.kind = kind
        super().__init__(kind)


class CalendarEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    etag: str = ""
    payload: dict
    recurring_event_id: str | None = None

    @property
    def cancelled(self) -> bool:
        return self.payload.get("status") == "cancelled"

    def interval(self) -> tuple[datetime, datetime] | None:
        if self.cancelled or self.payload.get("transparency") == "transparent":
            return None

        def instant(part):
            if "dateTime" in part:
                value = datetime.fromisoformat(part["dateTime"].replace("Z", "+00:00"))
                if value.tzinfo is None:
                    value = value.replace(tzinfo=ZoneInfo(part.get("timeZone", "UTC")))
                return value.astimezone(UTC)
            return datetime.combine(
                date.fromisoformat(part["date"]), time.min, ZoneInfo(part.get("timeZone", "UTC"))
            ).astimezone(UTC)

        try:
            start, end = instant(self.payload["start"]), instant(self.payload["end"])
        except (KeyError, ValueError, TypeError):
            raise ProviderError("PERMANENT_VALIDATION") from None
        if end <= start:
            raise ProviderError("PERMANENT_VALIDATION")
        return start, end


class CalendarPage(BaseModel):
    events: tuple[CalendarEvent, ...]
    next_page_token: str | None = None
    next_sync_token: str | None = None


class CalendarWriteResult(BaseModel):
    event: CalendarEvent


class CalendarProvider(Protocol):
    def list_events(
        self,
        calendar_id: str,
        *,
        sync_token: str | None = None,
        page_token: str | None = None,
        time_min: datetime,
        time_max: datetime,
    ) -> CalendarPage: ...
    def get_event(self, calendar_id: str, event_id: str) -> CalendarEvent: ...
    def create_event(self, calendar_id: str, payload: dict) -> CalendarWriteResult: ...
    def update_event(
        self, calendar_id: str, event_id: str, payload: dict, *, etag: str
    ) -> CalendarWriteResult: ...
    def delete_event(self, calendar_id: str, event_id: str, *, etag: str) -> None: ...


def parse_event(payload: dict, *, timezone: str = "UTC") -> CalendarEvent:
    # All-day events inherit the calendar's timezone, not the host timezone.
    data = dict(payload)
    for field in ("start", "end"):
        if field in data:
            data[field] = {"timeZone": timezone, **data[field]}
    return CalendarEvent(
        id=data["id"],
        etag=data.get("etag", ""),
        payload=data,
        recurring_event_id=data.get("recurringEventId"),
    )
