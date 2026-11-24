"""get_tenant() tested in isolation, on a tiny app with one protected route."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.tenant import CurrentTenant
from tests.tokens import auth_header, make_token

app = FastAPI()


@app.get("/whoami")
def whoami(tenant: CurrentTenant) -> dict[str, str]:
    return {"org": tenant.org, "userId": tenant.user_id, "email": tenant.email}


client = TestClient(app)


def _unsigned_token(claims: dict[str, object]) -> str:
    """An `alg: none` token: header and payload, empty signature."""

    def b64(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."


def test_valid_token_returns_tenant_from_the_token() -> None:
    res = client.get("/whoami", headers=auth_header(org="org_acme"))
    assert res.status_code == 200
    assert res.json() == {"org": "org_acme", "userId": "user_123", "email": "owner@example.com"}


def test_no_token_is_401_with_bearer_challenge() -> None:
    res = client.get("/whoami")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


def test_org_header_is_ignored_entirely() -> None:
    """The old project's bug: a header alone must never grant access."""
    assert client.get("/whoami", headers={"X-Organization-Id": "org_victim"}).status_code == 401

    res = client.get(
        "/whoami", headers={**auth_header(org="org_mine"), "X-Organization-Id": "org_victim"}
    )
    assert res.json()["org"] == "org_mine"


@pytest.mark.parametrize(
    ("label", "headers"),
    [
        ("expired", auth_header(expires_in=-10)),
        ("wrong secret", auth_header(secret="another-secret-that-is-also-32-chars-long")),
        ("wrong issuer", auth_header(iss="someone-else")),
        ("wrong audience", auth_header(aud="another-api")),
        ("other algorithm", auth_header(algorithm="HS512")),
        ("missing exp", auth_header(drop=("exp",))),
        ("missing org", auth_header(drop=("org",))),
        ("missing sub", auth_header(drop=("sub",))),
        ("bad org format", auth_header(org="org_a; DROP TABLE sources")),
        ("org too long", auth_header(org="o" * 65)),
        ("org not a string", auth_header(org=123)),
        ("garbage token", auth_header(token="not.a.jwt")),
        ("basic scheme", {"Authorization": "Basic dXNlcjpwYXNz"}),
        ("empty bearer", {"Authorization": "Bearer "}),
        (
            "alg none",
            auth_header(
                token=_unsigned_token(
                    {"iss": "quorix-web", "aud": "quorix-api", "sub": "u", "org": "org_x",
                     "email": "e", "iat": 0, "exp": 9_999_999_999}
                )
            ),
        ),
    ],
)
def test_bad_tokens_are_401(label: str, headers: dict[str, str]) -> None:
    res = client.get("/whoami", headers=headers)
    assert res.status_code == 401, label


def test_small_clock_skew_is_tolerated() -> None:
    """Expired 2 s ago, within the 5 s leeway: still accepted. (Expired 10 s ago is a 401 above.)"""
    res = client.get("/whoami", headers=auth_header(expires_in=-2))
    assert res.status_code == 200


def test_tampered_payload_is_401() -> None:
    """Change org in the payload but keep the old signature: the signature no longer matches."""
    header, _payload, signature = make_token(org="org_mine").split(".")
    forged = base64.urlsafe_b64encode(
        json.dumps({"iss": "quorix-web", "aud": "quorix-api", "sub": "user_123",
                    "org": "org_victim", "email": "x", "iat": 0, "exp": 9_999_999_999}).encode()
    ).rstrip(b"=").decode()
    res = client.get("/whoami", headers=auth_header(token=f"{header}.{forged}.{signature}"))
    assert res.status_code == 401
