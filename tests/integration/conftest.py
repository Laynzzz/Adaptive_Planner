"""Exercise the real local provider's login form and authorization-code callback."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from planner.app import create_app
from planner.settings import Settings


class LoginForm(HTMLParser):
    action = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "kc-form-login":
            self.action = attrs["action"]


def sign_in(api, username):
    start = api.get("/api/v1/auth/login", follow_redirects=False)
    assert start.status_code == 302, start.text
    with httpx.Client(follow_redirects=False, timeout=10) as provider:
        page = provider.get(start.headers["location"])
        # Browsers treat loopback as trustworthy; Python CookieJar does not.
        # Limit the transport adaptation to this real, local test provider.
        assert urlsplit(str(page.url)).hostname == "127.0.0.1"
        for provider_cookie in provider.cookies.jar:
            provider_cookie.secure = False
        form = LoginForm()
        form.feed(page.text)
        assert form.action, "OIDC login form missing"
        response = provider.post(
            form.action,
            data={"username": username, "password": f"local-{username}-only", "credentialId": ""},
        )
        assert response.status_code == 302, "OIDC login did not redirect"
        target = urlsplit(response.headers["location"])
        callback = api.get(target.path + "?" + target.query, follow_redirects=False)
        assert callback.status_code == 302, callback.text
    me = api.get("/api/v1/me")
    assert me.status_code == 200, me.text
    api.headers["X-CSRF-Token"] = me.json()["csrf_token"]
    return api


class AuthenticatedAPI:
    """Real session wrapper: CSRF remains validated and idempotency stays in its header."""

    def __init__(self, raw):
        self.raw = raw

    def __getattr__(self, name):
        method = getattr(self.raw, name)
        if name not in ("post", "put", "patch", "delete"):
            return method

        def mutate(*args, **kwargs):
            from uuid import uuid4

            headers = dict(kwargs.get("headers", {}))
            payload = kwargs.get("json")
            key = None
            if isinstance(payload, dict):
                payload = dict(payload)
                key = payload.pop("idempotency_key", None)
                kwargs["json"] = payload
            headers.setdefault("Idempotency-Key", key or str(uuid4()))
            kwargs["headers"] = headers
            return method(*args, **kwargs)

        return mutate


@pytest.fixture
def app(migrated_database_url):
    return create_app(Settings(database_url=migrated_database_url))


@pytest.fixture
def api_a(app):
    with TestClient(app, base_url="http://127.0.0.1:8000") as api:
        yield AuthenticatedAPI(sign_in(api, "demo-a"))


@pytest.fixture
def api_b(app):
    with TestClient(app, base_url="http://127.0.0.1:8000") as api:
        yield AuthenticatedAPI(sign_in(api, "demo-b"))
