"""Tenant resolution: the organization comes ONLY from a verified JWT (SPEC section 2).

There is deliberately no X-Organization-Id header, query parameter or body field.
Every failure is a 401 with the same generic message, so callers learn nothing about why.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

# auto_error=False: we raise our own 401 instead of FastAPI's default response.
# HTTPBearer also adds the "Authorize" button to /docs.
_bearer = HTTPBearer(auto_error=False)
_ORG_RE = re.compile(settings.org_id_pattern)
_REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub", "org", "email"]


@dataclass(frozen=True, slots=True)
class Tenant:
    """Who is calling. `org` scopes every SQL query, vector searches included."""

    org: str
    user_id: str
    email: str


def _unauthorized(detail: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_tenant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Tenant:
    """FastAPI dependency: verify the bearer token and return the caller's tenant."""
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.backend_jwt_secret,
            algorithms=[settings.jwt_algorithm],  # a fixed list: blocks "alg: none" and alg swaps
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": _REQUIRED_CLAIMS},
            leeway=settings.jwt_leeway_seconds,
        )
    except jwt.PyJWTError as exc:
        # Log the real reason for us; tell the caller nothing specific.
        logger.info("rejected token: %s", type(exc).__name__)
        raise _unauthorized() from None

    org, sub, email = claims["org"], claims["sub"], claims["email"]
    if not isinstance(org, str) or not _ORG_RE.fullmatch(org):
        logger.info("rejected token: bad org claim")
        raise _unauthorized()
    if not isinstance(sub, str) or not sub or not isinstance(email, str):
        logger.info("rejected token: bad sub/email claim")
        raise _unauthorized()

    return Tenant(org=org, user_id=sub, email=email)


# Shorthand for route signatures: `def list_sources(tenant: CurrentTenant, ...)`.
CurrentTenant = Annotated[Tenant, Depends(get_tenant)]


def get_writable_tenant(tenant: CurrentTenant) -> Tenant:
    """Like get_tenant, for routes that change data: read-only orgs (the public demo) get 403.

    403, not 401: the caller is authenticated, just not allowed to do this. Enforced here, on the
    server, so hiding buttons in the UI is a convenience, not the protection.
    """
    if tenant.org in settings.read_only_org_set:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The demo workspace is read-only.")
    return tenant


WritableTenant = Annotated[Tenant, Depends(get_writable_tenant)]
