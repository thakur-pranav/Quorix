"""The read-only demo org: every write route is refused on the server; reading and chat still work."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from tests.tokens import auth_header

DEMO, OTHER = auth_header(org="org_demo"), auth_header(org="org_other")

WRITES = [
    ("post", "/api/sources", {"json": {"location": "https://docs.example.com"}}),
    ("post", "/api/sources/upload", {"files": {"file": ("notes.txt", b"hello", "text/plain")}}),
    ("post", "/api/sources/src_000000000001/reindex", {}),
    ("delete", "/api/sources/src_000000000001", {}),
    ("post", "/api/analytics/run", {"json": {}}),
]


@pytest.fixture(autouse=True)
def demo_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "read_only_orgs", "org_demo, org_showcase")


@pytest.mark.parametrize(("method", "path", "kwargs"), WRITES, ids=[f"{m} {p}" for m, p, _ in WRITES])
def test_every_write_route_is_refused_for_a_read_only_org(client: TestClient, method: str, path: str, kwargs: dict) -> None:
    res = getattr(client, method)(path, headers=DEMO, **kwargs)
    assert res.status_code == 403  # authenticated, but not allowed: not 401
    assert res.json()["detail"] == "The demo workspace is read-only."


def test_reading_and_chat_still_work(client: TestClient) -> None:
    assert client.get("/api/sources", headers=DEMO).status_code == 200
    assert client.get("/api/overview", headers=DEMO).status_code == 200
    assert client.post("/api/chat", headers=DEMO, json={"question": "Refunds?", "sessionId": "s1"}).status_code == 200


def test_other_orgs_can_still_write(client: TestClient) -> None:
    assert client.post("/api/analytics/run", headers=OTHER, json={}).status_code == 202


def test_the_setting_parses_a_comma_list() -> None:
    assert settings.read_only_org_set == frozenset({"org_demo", "org_showcase"})
