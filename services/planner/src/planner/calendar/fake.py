"""Deterministic synthetic provider for local demos and fault-boundary tests."""

from copy import deepcopy

from planner.calendar.provider import CalendarPage, CalendarWriteResult, ProviderError, parse_event


class FakeCalendarProvider:
    def __init__(self, *, page_size=2):
        self.events = {}
        self.version = 0
        self.changes = []
        self.page_size = page_size
        self.fail_on_page = None
        self.timeout_after_write = False
        self.invalid_token_once = False
        self.authentication_required = False
        self.after_write = None
        self.writes = []

    def put_external(self, payload):
        self.version += 1
        data = deepcopy(payload)
        data["etag"] = str(self.version)
        self.events[data["id"]] = data
        self.changes.append((self.version, data))
        return parse_event(data)

    def _check(self):
        if self.authentication_required:
            raise ProviderError("AUTHENTICATION_REQUIRED")

    def list_events(self, calendar_id, *, sync_token=None, page_token=None, time_min, time_max):
        self._check()
        if sync_token and self.invalid_token_once:
            self.invalid_token_once = False
            raise ProviderError("INVALID_SYNC_TOKEN")
        offset = int(page_token or 0)
        if self.fail_on_page == offset // self.page_size + 1:
            raise ProviderError("RETRYABLE")
        source = (
            [p for v, p in self.changes if v > int(sync_token)]
            if sync_token
            else list(self.events.values())
        )
        end = offset + self.page_size
        return CalendarPage(
            events=tuple(parse_event(p) for p in source[offset:end]),
            next_page_token=str(end) if end < len(source) else None,
            next_sync_token=str(self.version) if end >= len(source) else None,
        )

    def get_event(self, calendar_id, event_id):
        self._check()
        data = self.events.get(event_id)
        if not data or data.get("status") == "cancelled":
            raise ProviderError("NOT_FOUND")
        return parse_event(deepcopy(data))

    def _written(self, method, payload):
        event = self.put_external(payload)
        self.writes.append((method, event.id))
        if self.after_write:
            callback, self.after_write = self.after_write, None
            callback()
        if self.timeout_after_write:
            self.timeout_after_write = False
            raise ProviderError("AMBIGUOUS_WRITE")
        return CalendarWriteResult(event=event)

    def create_event(self, calendar_id, payload):
        self._check()
        if payload["id"] in self.events and self.events[payload["id"]].get("status") != "cancelled":
            raise ProviderError("CONFLICT")
        return self._written("CREATE", payload)

    def update_event(self, calendar_id, event_id, payload, *, etag):
        event = self.get_event(calendar_id, event_id)
        if event.etag != etag:
            raise ProviderError("CONFLICT")
        return self._written("UPDATE", {**payload, "id": event_id})

    def delete_event(self, calendar_id, event_id, *, etag):
        event = self.get_event(calendar_id, event_id)
        if event.etag != etag:
            raise ProviderError("CONFLICT")
        self._written("DELETE", {"id": event_id, "status": "cancelled"})


class DurableMockProvider:
    """Synthetic remote state survives local worker restarts and is owner-scoped."""

    def __init__(self, engine, owner_id):
        self.engine, self.owner_id = engine, owner_id

    def _call(self, name, *args, **kwargs):
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from planner.db.calendar_models import CalendarConnection

        with Session(self.engine) as db, db.begin():
            connection = db.scalar(
                select(CalendarConnection)
                .where(CalendarConnection.owner_id == self.owner_id)
                .with_for_update()
            )
            fake = FakeCalendarProvider()
            state = connection.mock_state or {}
            fake.events = deepcopy(state.get("events", {}))
            fake.version = state.get("version", 0)
            fake.changes = deepcopy(state.get("changes", []))
            result = getattr(fake, name)(*args, **kwargs)
            connection.mock_state = {
                "events": fake.events,
                "version": fake.version,
                "changes": fake.changes,
            }
            return result

    def list_events(self, *args, **kwargs):
        return self._call("list_events", *args, **kwargs)

    def get_event(self, *args, **kwargs):
        return self._call("get_event", *args, **kwargs)

    def create_event(self, *args, **kwargs):
        return self._call("create_event", *args, **kwargs)

    def update_event(self, *args, **kwargs):
        return self._call("update_event", *args, **kwargs)

    def delete_event(self, *args, **kwargs):
        return self._call("delete_event", *args, **kwargs)
