"""Google Calendar HTTP adapter. Constructed only after separate calendar OAuth."""

from collections.abc import Callable
from datetime import datetime
from urllib.parse import quote

import httpx

from planner.calendar.provider import CalendarPage, CalendarWriteResult, ProviderError, parse_event


class GoogleCalendarProvider:
    def __init__(self, token_supplier: Callable[[], str], *, client: httpx.Client | None = None):
        self.token_supplier = token_supplier
        self.client = client or httpx.Client(timeout=10)

    def _request(self, method, calendar_id, event_id=None, *, params=None, payload=None, etag=None):
        url = "https://www.googleapis.com/calendar/v3/calendars/" + quote(calendar_id, safe="")
        url += "/events" + ("/" + quote(event_id, safe="") if event_id else "")
        headers = {"Authorization": "Bearer " + self.token_supplier()}
        if etag is not None:
            headers["If-Match"] = etag
        try:
            response = self.client.request(
                method, url, params=params, json=payload, headers=headers
            )
        except httpx.TransportError:
            raise ProviderError("RETRYABLE" if method == "GET" else "AMBIGUOUS_WRITE") from None
        if response.status_code >= 400:
            kind = {
                401: "AUTHENTICATION_REQUIRED",
                403: "PERMANENT_VALIDATION",
                404: "NOT_FOUND",
                409: "CONFLICT",
                410: "INVALID_SYNC_TOKEN",
                412: "CONFLICT",
                429: "RETRYABLE",
            }.get(
                response.status_code,
                "RETRYABLE" if response.status_code >= 500 else "PERMANENT_VALIDATION",
            )
            raise ProviderError(kind)
        return response.json() if response.content else {}

    def list_events(
        self,
        calendar_id: str,
        *,
        sync_token=None,
        page_token=None,
        time_min: datetime,
        time_max: datetime,
    ) -> CalendarPage:
        params = {"singleEvents": "true", "showDeleted": "true", "maxResults": "250"}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            params.update(timeMin=time_min.isoformat(), timeMax=time_max.isoformat())
        if page_token:
            params["pageToken"] = page_token
        data = self._request("GET", calendar_id, params=params)
        return CalendarPage(
            events=tuple(
                parse_event(p, timezone=data.get("timeZone", "UTC")) for p in data.get("items", ())
            ),
            next_page_token=data.get("nextPageToken"),
            next_sync_token=data.get("nextSyncToken"),
        )

    def get_event(self, calendar_id, event_id):
        return parse_event(self._request("GET", calendar_id, event_id))

    def create_event(self, calendar_id, payload):
        return CalendarWriteResult(
            event=parse_event(self._request("POST", calendar_id, payload=payload))
        )

    def update_event(self, calendar_id, event_id, payload, *, etag):
        return CalendarWriteResult(
            event=parse_event(
                self._request("PUT", calendar_id, event_id, payload=payload, etag=etag)
            )
        )

    def delete_event(self, calendar_id, event_id, *, etag):
        self._request("DELETE", calendar_id, event_id, etag=etag)
