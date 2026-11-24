from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Source
from app.schemas import ChatRequest, ChatResponse, HealthOut, SourceCreate, SourceOut


def test_responses_are_camel_case() -> None:
    out = HealthOut(indexed_chunks=3, llm_provider="groq").model_dump(by_alias=True)
    assert out == {"status": "ok", "indexedChunks": 3, "llmProvider": "groq"}


def test_requests_accept_camel_case() -> None:
    req = ChatRequest.model_validate({"question": "How do refunds work?", "sessionId": "abc-123"})
    assert req.session_id == "abc-123"


def test_request_rejects_client_sent_organization_id() -> None:
    with pytest.raises(ValidationError, match="organizationId"):
        ChatRequest.model_validate(
            {"question": "hi", "sessionId": "s1", "organizationId": "org_victim"}
        )


@pytest.mark.parametrize("question", ["", "   ", "x" * (settings.max_question_chars + 1)])
def test_question_must_be_non_blank_and_bounded(question: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question=question, session_id="s1")


def test_question_is_stripped() -> None:
    assert ChatRequest(question="  hi  ", session_id="s1").question == "hi"


@pytest.mark.parametrize("session_id", ["", "has space", "a" * 65, "semi;colon"])
def test_session_id_format(session_id: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question="hi", session_id=session_id)


@pytest.mark.parametrize(
    "location", ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)", "not a url"]
)
def test_source_location_must_be_http_or_https(location: str) -> None:
    with pytest.raises(ValidationError):
        SourceCreate.model_validate({"kind": "website", "location": location})


def test_source_create_accepts_https_and_optional_label() -> None:
    src = SourceCreate.model_validate({"kind": "website", "location": "https://docs.example.com"})
    assert src.location.scheme == "https"
    assert src.label is None


def test_source_out_from_orm_hides_internal_fields(db: Session) -> None:
    row = Source(
        organization_id="org_a", kind="website", label="Docs", location="https://example.com"
    )
    db.add(row)
    db.commit()

    out = SourceOut.model_validate(row).model_dump(by_alias=True)
    assert out["id"] == row.id
    assert out["pageCount"] == 0 and out["createdAt"] is not None
    assert "organizationId" not in out and "contentHash" not in out


def test_chat_response_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ChatResponse(
            id="msg_000000000001",
            text="x",
            created_at=datetime.now(timezone.utc),
            confidence=1.5,
            low_confidence=False,
        )
