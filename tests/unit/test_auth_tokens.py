"""JWT negative controls exercise the same verifier used by the real callback."""

from datetime import UTC, datetime

import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey

from planner.api.auth import verify_id_token
from planner.settings import Settings


@pytest.fixture(scope="module")
def signing_key():
    return RSAKey.generate_key(2048, parameters={"kid": "local-test-signing-key"})


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "https://wrong-issuer.example"},
        {"aud": "wrong-client"},
        {"nonce": "wrong-nonce"},
        {"exp": 1},
        {"sub": None},
    ],
)
def test_invalid_claims_cannot_create_identity(signing_key, change):
    config = Settings()
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": config.oidc_issuer,
        "aud": config.oidc_client_id,
        "sub": "synthetic",
        "nonce": "expected-nonce",
        "iat": now,
        "exp": now + 300,
        **change,
    }
    token = {
        "id_token": jwt.encode(
            {"alg": "RS256", "kid": "local-test-signing-key"}, claims, signing_key
        ),
        "access_token": "synthetic-unused",
    }
    with pytest.raises(JoseError):
        verify_id_token(
            token, {"keys": [signing_key.as_dict(private=False)]}, config, "expected-nonce"
        )


def test_wrong_signature_cannot_create_identity(signing_key):
    other = RSAKey.generate_key(2048, parameters={"kid": "local-test-signing-key"})
    config = Settings()
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": config.oidc_issuer,
        "aud": config.oidc_client_id,
        "sub": "synthetic",
        "nonce": "expected-nonce",
        "iat": now,
        "exp": now + 300,
    }
    token = {
        "id_token": jwt.encode({"alg": "RS256", "kid": "local-test-signing-key"}, claims, other),
        "access_token": "synthetic-unused",
    }
    with pytest.raises(JoseError):
        verify_id_token(
            token, {"keys": [signing_key.as_dict(private=False)]}, config, "expected-nonce"
        )
