from datetime import UTC, datetime

import httpx
import pytest


def test_google_expands_recurrence_and_uses_sync_paging_without_time_filters():
    from planner.calendar.google import GoogleCalendarProvider

    observed = []

    def handle(request):
        observed.append(request)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "instance",
                        "etag": "v1",
                        "recurringEventId": "series",
                        "start": {"dateTime": "2026-09-25T09:00:00Z"},
                        "end": {"dateTime": "2026-09-25T10:00:00Z"},
                    }
                ],
                "nextSyncToken": "next",
            },
        )

    provider = GoogleCalendarProvider(
        lambda: "synthetic-token", client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    page = provider.list_events(
        "calendar",
        sync_token="old",
        page_token="page2",
        time_min=datetime(2026, 9, 25, tzinfo=UTC),
        time_max=datetime(2026, 10, 9, tzinfo=UTC),
    )
    assert page.events[0].recurring_event_id == "series"
    assert observed[0].url.params["singleEvents"] == "true"
    assert observed[0].url.params["syncToken"] == "old"
    assert observed[0].url.params["pageToken"] == "page2"
    assert "timeMin" not in observed[0].url.params
    assert page.next_sync_token == "next"


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (410, "INVALID_SYNC_TOKEN"),
        (401, "AUTHENTICATION_REQUIRED"),
        (429, "RETRYABLE"),
        (412, "CONFLICT"),
    ],
)
def test_google_errors_keep_recovery_semantics(status, kind):
    from planner.calendar.google import GoogleCalendarProvider
    from planner.calendar.provider import ProviderError

    provider = GoogleCalendarProvider(
        lambda: "synthetic-token",
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status))),
    )
    with pytest.raises(ProviderError) as error:
        provider.list_events(
            "calendar",
            time_min=datetime(2026, 9, 25, tzinfo=UTC),
            time_max=datetime(2026, 10, 9, tzinfo=UTC),
        )
    assert error.value.kind == kind


def test_google_conditional_write_and_ambiguous_timeout_are_distinct():
    from planner.calendar.google import GoogleCalendarProvider
    from planner.calendar.provider import ProviderError

    def handle(request):
        assert request.headers["If-Match"] == "expected-etag"
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    provider = GoogleCalendarProvider(
        lambda: "synthetic-token", client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    with pytest.raises(ProviderError) as error:
        provider.update_event("calendar", "event", {}, etag="expected-etag")
    assert error.value.kind == "AMBIGUOUS_WRITE"
