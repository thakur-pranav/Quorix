"""The real app end to end: health, auth on protected routes, tenant isolation, CORS, docs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Source
from tests.tokens import auth_header


def _add_source(db: Session, org: str, label: str, minutes_ago: int = 0) -> Source:
    src = Source(
        organization_id=org,
        kind="website",
        label=label,
        location=f"https://{label.lower()}.example.com",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.add(src)
    db.commit()
    return src


# --- Health ---------------------------------------------------------------------------------


def test_health_is_public_and_camel_case(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "indexedChunks": 0, "llmProvider": "none"}


# --- Auth on protected routes (ROADMAP Day 1 tests) -----------------------------------------


@pytest.mark.parametrize(
    ("label", "headers"),
    [
        ("no token", {}),
        ("expired", auth_header(expires_in=-60)),
        ("wrong secret", auth_header(secret="x" * 64)),
        ("org header only", {"X-Organization-Id": "org_a"}),
    ],
)
def test_protected_route_rejects_bad_auth(client: TestClient, label: str, headers: dict[str, str]) -> None:
    res = client.get("/api/sources", headers=headers)
    assert res.status_code == 401, label
    assert res.json() == {"detail": res.json()["detail"]}  # FastAPI error shape, nothing extra


def test_protected_route_accepts_valid_token(client: TestClient) -> None:
    res = client.get("/api/sources", headers=auth_header(org="org_a"))
    assert res.status_code == 200
    assert res.json() == []


def test_unknown_api_route_is_404_not_401(client: TestClient) -> None:
    assert client.get("/api/nope", headers=auth_header()).status_code == 404


# --- Tenant isolation -----------------------------------------------------------------------


def test_sources_are_isolated_per_org_and_newest_first(client: TestClient, db: Session) -> None:
    _add_source(db, "org_a", "Old", minutes_ago=10)
    _add_source(db, "org_a", "New", minutes_ago=1)
    _add_source(db, "org_b", "Secret")

    res = client.get("/api/sources", headers=auth_header(org="org_a"))
    assert res.status_code == 200
    body = res.json()
    assert [s["label"] for s in body] == ["New", "Old"]
    assert all("organizationId" not in s for s in body)

    other = client.get("/api/sources", headers=auth_header(org="org_b")).json()
    assert [s["label"] for s in other] == ["Secret"]


def test_org_header_cannot_override_token_org(client: TestClient, db: Session) -> None:
    _add_source(db, "org_b", "Secret")
    res = client.get(
        "/api/sources", headers={**auth_header(org="org_a"), "X-Organization-Id": "org_b"}
    )
    assert res.json() == []


# --- CORS -----------------------------------------------------------------------------------


def _preflight(client: TestClient, origin: str) -> dict[str, str]:
    res = client.options(
        "/api/sources",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    return dict(res.headers)


def test_cors_allows_the_frontend_origin(client: TestClient) -> None:
    headers = _preflight(client, "http://localhost:3000")
    assert headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_refuses_other_origins(client: TestClient) -> None:
    headers = _preflight(client, "https://evil.example.com")
    assert "access-control-allow-origin" not in headers


# --- Docs -----------------------------------------------------------------------------------


def test_openapi_documents_bearer_auth(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert "/api/health" in spec["paths"] and "/api/sources" in spec["paths"]
    schemes = spec["components"]["securitySchemes"]
    assert any(s.get("scheme", "").lower() == "bearer" for s in schemes.values())
