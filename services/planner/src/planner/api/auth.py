"""OIDC authorization code/PKCE login and opaque database-backed BFF sessions."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from authlib.oidc.core import CodeIDToken
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from joserfc import jwt
from joserfc.jwk import KeySet
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from planner.api.errors import APIError
from planner.api.schemas import MeResponse
from planner.db.models import BrowserSession, Identity, LoginFlow, PlanningState

router = APIRouter(prefix="/api/v1")
SESSION_COOKIE = "planner_session"
FLOW_COOKIE = "planner_login"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Principal:
    owner_id: UUID
    csrf_token: str
    token_hash: str


def require_session(request: Request) -> Principal:
    token_hash = digest(request.cookies.get(SESSION_COOKIE, ""))
    with Session(request.app.state.engine) as db:
        session = db.get(BrowserSession, token_hash)
        if session is None or session.expires_at <= now():
            raise APIError("AUTH_REQUIRED", 401, "Sign in to continue.")
        return Principal(session.owner_id, session.csrf_token, token_hash)


def require_mutation(
    request: Request, principal: Principal = Depends(require_session)
) -> Principal:
    token = request.headers.get("X-CSRF-Token", "")
    if not secrets.compare_digest(token, principal.csrf_token):
        raise APIError("CSRF_INVALID", 403, "Refresh this page before making changes.")
    origin = request.headers.get("origin")
    config = request.app.state.settings
    if origin and origin not in (config.app_origin, config.ui_origin):
        raise APIError("ORIGIN_INVALID", 403, "This request origin is not allowed.")
    return principal


def metadata(config):
    with httpx.Client(timeout=10) as client:
        response = client.get(config.oidc_issuer + "/.well-known/openid-configuration")
        response.raise_for_status()
        result = response.json()
    if result.get("issuer") != config.oidc_issuer:
        raise ValueError("Issuer mismatch")
    return result


def cookie(response, key, value, config, max_age):
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        secure=config.secure_cookies,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


@router.get("/auth/login")
def login(request: Request):
    config = request.app.state.settings
    try:
        provider = metadata(config)
    except (httpx.HTTPError, ValueError):
        raise APIError(
            "OIDC_UNAVAILABLE", 503, "Sign-in provider is unavailable.", retryable=True
        ) from None
    flow_token, state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    with Session(request.app.state.engine) as db, db.begin():
        db.execute(delete(LoginFlow).where(LoginFlow.expires_at < now()))
        db.add(
            LoginFlow(
                token_hash=digest(flow_token),
                state=state,
                nonce=nonce,
                verifier=verifier,
                expires_at=now() + timedelta(minutes=5),
            )
        )
    with OAuth2Client(
        config.oidc_client_id,
        code_challenge_method="S256",
        redirect_uri=config.app_origin + "/api/v1/auth/callback",
    ) as client:
        url, _ = client.create_authorization_url(
            provider["authorization_endpoint"],
            state=state,
            nonce=nonce,
            code_verifier=verifier,
            scope="openid profile",
            prompt="login",
        )
    response = RedirectResponse(url, status_code=302)
    cookie(response, FLOW_COOKIE, flow_token, config, 300)
    return response


def verify_id_token(token, keys, config, nonce):
    decoded = jwt.decode(token["id_token"], KeySet.import_key_set(keys), algorithms=["RS256"])
    claims = CodeIDToken(
        decoded.claims,
        decoded.header,
        options={"iss": {"value": config.oidc_issuer}, "aud": {"value": config.oidc_client_id}},
        params={
            "nonce": nonce,
            "client_id": config.oidc_client_id,
            "access_token": token["access_token"],
        },
    )
    claims.validate(leeway=30)
    return claims


@router.get("/auth/callback")
def callback(request: Request, code: str = "", state: str = ""):
    config = request.app.state.settings
    with Session(request.app.state.engine, expire_on_commit=False) as db, db.begin():
        flow = db.get(LoginFlow, digest(request.cookies.get(FLOW_COOKIE, "")), with_for_update=True)
        if (
            flow is None
            or flow.expires_at <= now()
            or not code
            or not secrets.compare_digest(flow.state, state)
        ):
            raise APIError(
                "LOGIN_STATE_INVALID", 400, "Restart sign-in; the login state is invalid."
            )
        db.delete(flow)
    try:
        provider = metadata(config)
        with OAuth2Client(
            config.oidc_client_id,
            token_endpoint_auth_method="none",
            timeout=10,
            redirect_uri=config.app_origin + "/api/v1/auth/callback",
        ) as client:
            token = client.fetch_token(
                provider["token_endpoint"], code=code, code_verifier=flow.verifier
            )
            keys_response = httpx.get(provider["jwks_uri"], timeout=10)
            keys_response.raise_for_status()
        claims = verify_id_token(token, keys_response.json(), config, flow.nonce)
    except Exception:
        # Authlib/Jose token failures carry provider payloads; never expose them.
        raise APIError(
            "LOGIN_INVALID", 400, "Sign-in could not be verified. Restart sign-in."
        ) from None
    opaque = secrets.token_urlsafe(32)
    with Session(request.app.state.engine) as db, db.begin():
        owner = db.execute(
            insert(Identity)
            .values(
                issuer=config.oidc_issuer,
                subject=claims["sub"],
                name=claims.get("name") or claims["sub"],
                timezone="UTC",
            )
            .on_conflict_do_update(
                index_elements=["issuer", "subject"],
                set_={"name": claims.get("name") or claims["sub"]},
            )
            .returning(Identity.id)
        ).scalar_one()
        db.execute(
            insert(PlanningState)
            .values(owner_id=owner, revision=0)
            .on_conflict_do_nothing(index_elements=["owner_id"])
        )
        db.execute(
            delete(BrowserSession).where(
                BrowserSession.token_hash == digest(request.cookies.get(SESSION_COOKIE, ""))
            )
        )
        db.add(
            BrowserSession(
                token_hash=digest(opaque),
                owner_id=owner,
                csrf_token=secrets.token_urlsafe(32),
                expires_at=now() + timedelta(hours=config.session_hours),
            )
        )
    response = RedirectResponse(config.ui_origin, status_code=302)
    cookie(response, SESSION_COOKIE, opaque, config, config.session_hours * 3600)
    response.delete_cookie(FLOW_COOKIE)
    return response


@router.get("/me", response_model=MeResponse)
def me(request: Request, principal: Principal = Depends(require_session)):
    with Session(request.app.state.engine) as db:
        identity = db.get(Identity, principal.owner_id)
        state = db.get(PlanningState, principal.owner_id)
        return {
            "id": str(identity.id),
            "name": identity.name,
            "timezone": identity.timezone,
            "revision": state.revision,
            "csrf_token": principal.csrf_token,
            "capabilities": ["tasks", "availability", "fixed_events"],
        }


@router.post("/auth/logout", status_code=204)
def logout(request: Request, principal: Principal = Depends(require_mutation)):
    with Session(request.app.state.engine) as db, db.begin():
        db.execute(delete(BrowserSession).where(BrowserSession.token_hash == principal.token_hash))
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE)
    return response
