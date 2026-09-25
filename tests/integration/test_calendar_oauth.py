# ruff: noqa: F811 -- imported pytest fixtures are deliberately injected by name.
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from planner.api.errors import APIError
from planner.calendar.oauth import CalendarConfig, begin_oauth, exchange_callback, google_provider
from planner.calendar.provider import ProviderError
from planner.db.calendar_models import CalendarConnection, CalendarOAuthFlow
from tests.integration.test_calendar_sync import calendar_scenario  # noqa: F401
from tests.integration.test_jobs import NOW


def configuration():
    return CalendarConfig(
        live_enabled=True,
        client_id="synthetic-client",
        client_secret="synthetic-secret",
        encryption_key=Fernet.generate_key().decode(),
    )


def test_calendar_oauth_is_separate_browser_bound_pkce_and_encrypts_refresh(calendar_scenario):
    engine, owner, _ = calendar_scenario
    config = configuration()
    with Session(engine) as db, db.begin():
        url = begin_oauth(db, owner, "browser-a", "synthetic", config, NOW)
    query = parse_qs(urlsplit(url).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["https://www.googleapis.com/auth/calendar.events"]
    assert "nonce" not in query  # This does not establish a login identity.
    state = query["state"][0]
    requests = []

    def response(request):
        requests.append(request)
        assert b"code_verifier=" in request.content
        return httpx.Response(
            200, json={"refresh_token": "synthetic-refresh", "access_token": "synthetic-access"}
        )

    client = httpx.Client(transport=httpx.MockTransport(response))
    with pytest.raises(APIError):
        exchange_callback(
            engine, owner, "browser-b", state, "synthetic-code", config, lambda: NOW, client=client
        )
    assert requests == []
    calendar_id, encrypted = exchange_callback(
        engine, owner, "browser-a", state, "synthetic-code", config, lambda: NOW, client=client
    )
    assert calendar_id == "synthetic"
    assert encrypted != "synthetic-refresh"
    assert (
        Fernet(config.encryption_key.encode()).decrypt(encrypted.encode()) == b"synthetic-refresh"
    )
    with pytest.raises(APIError):
        exchange_callback(
            engine, owner, "browser-a", state, "synthetic-code", config, lambda: NOW, client=client
        )
    assert len(requests) == 1


def test_expired_calendar_oauth_state_never_exchanges_code(calendar_scenario):
    engine, owner, _ = calendar_scenario
    config = configuration()
    with Session(engine) as db, db.begin():
        db.add(
            CalendarOAuthFlow(
                state_hash=hashlib.sha256(b"old-state").hexdigest(),
                owner_id=owner,
                browser_session_hash="browser",
                verifier="verifier",
                calendar_id="synthetic",
                expires_at=NOW - timedelta(seconds=1),
            )
        )
    with pytest.raises(APIError):
        exchange_callback(
            engine,
            owner,
            "browser",
            "old-state",
            "code",
            config,
            lambda: NOW,
            client=httpx.Client(
                transport=httpx.MockTransport(lambda r: pytest.fail("Unexpected exchange"))
            ),
        )


@pytest.mark.parametrize(
    ("status", "expected"),
    [(400, "AUTHENTICATION_REQUIRED"), (429, "RETRYABLE"), (503, "RETRYABLE")],
)
def test_refresh_errors_keep_auth_distinct_from_temporary_failures(
    calendar_scenario, status, expected
):
    engine, owner, _ = calendar_scenario
    config = configuration()
    with Session(engine) as db, db.begin():
        connection = db.get(CalendarConnection, owner)
        connection.provider = "GOOGLE"
        connection.encrypted_refresh_token = (
            Fernet(config.encryption_key.encode()).encrypt(b"synthetic-refresh").decode()
        )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json={"error": "redacted"}))
    )
    provider = google_provider(engine, owner, config, lambda: NOW, client=client)
    with pytest.raises(ProviderError) as error:
        provider.get_event("synthetic", "event")
    assert str(error.value) == expected
