from __future__ import annotations

from fastapi.testclient import TestClient

from tests.tokens import auth_header


def test_chat_requires_a_token(client: TestClient) -> None:
    res = client.post("/api/chat", json={"question": "hi", "sessionId": "s1"})
    assert res.status_code == 401


def test_chat_validates_input(client: TestClient) -> None:
    res = client.post("/api/chat", headers=auth_header(), json={"question": "   ", "sessionId": "s1"})
    assert res.status_code == 422


def test_chat_returns_the_camel_case_contract(client: TestClient) -> None:
    res = client.post("/api/chat", headers=auth_header(), json={"question": "hi", "sessionId": "s1"})
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"id", "role", "text", "createdAt", "confidence", "lowConfidence", "citations"}
    assert body["role"] == "assistant" and body["id"].startswith("msg_")
