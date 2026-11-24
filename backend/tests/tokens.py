"""Test helper: sign service tokens exactly like the Next.js server will (SPEC section 2).

Imports only PyJWT, never `app`, so conftest.py can import it before the app's settings load.
"""

from __future__ import annotations

import time
from typing import Any

import jwt

# 64+ chars, so even the HS512 test token uses a key long enough for HS512 (RFC 7518 3.2).
TEST_JWT_SECRET = "test-secret-for-quorix-service-tokens-0123456789-abcdefghijklmnop"


def make_token(
    org: str = "org_test",
    *,
    secret: str = TEST_JWT_SECRET,
    algorithm: str = "HS256",
    expires_in: int = 60,
    drop: tuple[str, ...] = (),
    **overrides: Any,
) -> str:
    """A valid token by default. Override or drop claims to build invalid ones."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": "quorix-web",
        "aud": "quorix-api",
        "sub": "user_123",
        "org": org,
        "email": "owner@example.com",
        "iat": now,
        "exp": now + expires_in,
    }
    claims.update(overrides)
    for name in drop:
        claims.pop(name, None)
    return jwt.encode(claims, secret, algorithm=algorithm)


def auth_header(token: str | None = None, **kwargs: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {token if token is not None else make_token(**kwargs)}"}
