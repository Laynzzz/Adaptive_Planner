"""Separate calendar authorization with browser-bound PKCE and encrypted refresh tokens."""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.api.errors import APIError
from planner.calendar.google import GoogleCalendarProvider
from planner.calendar.provider import ProviderError
from planner.db.calendar_models import CalendarConnection, CalendarOAuthFlow


@dataclass(frozen=True)
class CalendarConfig:
    live_enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://127.0.0.1:8000/api/v1/calendar/callback"
    encryption_key: str = ""

    @property
    def configured(self):
        if not (
            self.live_enabled and self.client_id and self.client_secret and self.encryption_key
        ):
            return False
        try:
            Fernet(self.encryption_key.encode())
        except (ValueError, TypeError):
            return False
        return True


def begin_oauth(db, owner, session_hash, calendar_id, config, now):
    if not config.configured:
        raise APIError(
            "CALENDAR_NOT_CONFIGURED", 503, "Live Google calendar access is not configured."
        )
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    db.add(
        CalendarOAuthFlow(
            state_hash=hashlib.sha256(state.encode()).hexdigest(),
            owner_id=owner,
            browser_session_hash=session_hash,
            verifier=verifier,
            calendar_id=calendar_id,
            expires_at=now + timedelta(minutes=10),
        )
    )
    db.get(CalendarConnection, owner).oauth_state_hash = hashlib.sha256(state.encode()).hexdigest()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/calendar.events",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )


def exchange_callback(engine, owner, session_hash, state, code, config, clock, *, client=None):
    if not config.configured:
        raise APIError(
            "CALENDAR_NOT_CONFIGURED", 503, "Live Google calendar access is not configured."
        )
    with Session(engine) as db, db.begin():
        flow = db.scalar(
            select(CalendarOAuthFlow)
            .where(CalendarOAuthFlow.state_hash == hashlib.sha256(state.encode()).hexdigest())
            .with_for_update()
        )
        if (
            not flow
            or flow.owner_id != owner
            or flow.browser_session_hash != session_hash
            or flow.expires_at <= clock()
        ):
            raise APIError(
                "CALENDAR_OAUTH_INVALID", 400, "Restart calendar authorization in this browser."
            )
        verifier, calendar_id = flow.verifier, flow.calendar_id
        db.delete(flow)
    transport = client or httpx.Client(timeout=10)
    try:
        response = transport.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "redirect_uri": config.redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        if response.status_code != 200 or not response.json().get("refresh_token"):
            raise APIError(
                "CALENDAR_OAUTH_FAILED",
                400,
                "Calendar authorization failed. Restart the connection.",
            )
        encrypted = (
            Fernet(config.encryption_key.encode())
            .encrypt(response.json()["refresh_token"].encode())
            .decode()
        )
        return calendar_id, encrypted
    except httpx.TransportError:
        raise APIError(
            "CALENDAR_OAUTH_FAILED",
            502,
            "Calendar authorization failed. Restart the connection.",
            retryable=True,
        ) from None
    finally:
        if client is None:
            transport.close()


def google_provider(engine, owner, config, clock, *, client=None):
    if not config.configured:
        raise ProviderError("AUTHENTICATION_REQUIRED")
    transport = client or httpx.Client(timeout=10)
    cached = {}

    def token():
        if cached.get("until") and cached["until"] > clock():
            return cached["access"]
        with Session(engine) as db:
            connection = db.get(CalendarConnection, owner)
            if (
                connection.state not in ("CONNECTED", "DISCONNECTING")
                or not connection.encrypted_refresh_token
            ):
                raise ProviderError("AUTHENTICATION_REQUIRED")
            try:
                refresh = (
                    Fernet(config.encryption_key.encode())
                    .decrypt(connection.encrypted_refresh_token.encode())
                    .decode()
                )
            except (InvalidToken, ValueError):
                raise ProviderError("AUTHENTICATION_REQUIRED") from None
        try:
            response = transport.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
            )
        except httpx.TransportError:
            raise ProviderError("RETRYABLE") from None
        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderError("RETRYABLE")
        if response.status_code != 200 or not response.json().get("access_token"):
            raise ProviderError("AUTHENTICATION_REQUIRED")
        data = response.json()
        cached.update(
            access=data["access_token"],
            until=clock() + timedelta(seconds=max(1, int(data.get("expires_in", 300)) - 30)),
        )
        if data.get("refresh_token"):
            with Session(engine) as db, db.begin():
                connection = db.get(CalendarConnection, owner)
                if connection.state in ("CONNECTED", "DISCONNECTING"):
                    connection.encrypted_refresh_token = (
                        Fernet(config.encryption_key.encode())
                        .encrypt(data["refresh_token"].encode())
                        .decode()
                    )
        return cached["access"]

    provider = GoogleCalendarProvider(token, client=transport)

    def revoke():
        with Session(engine) as db:
            connection = db.get(CalendarConnection, owner)
            if not connection.encrypted_refresh_token:
                return
            try:
                refresh = (
                    Fernet(config.encryption_key.encode())
                    .decrypt(connection.encrypted_refresh_token.encode())
                    .decode()
                )
            except (InvalidToken, ValueError):
                raise ProviderError("AUTHENTICATION_REQUIRED") from None
        try:
            response = transport.post(
                "https://oauth2.googleapis.com/revoke", data={"token": refresh}
            )
        except httpx.TransportError:
            raise ProviderError("RETRYABLE") from None
        if response.status_code != 200:
            raise ProviderError("RETRYABLE")

    provider.revoke_credentials = revoke
    return provider
