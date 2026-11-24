"""Pydantic request and response models (SPEC section 4).

Python fields are snake_case; JSON is camelCase (the frontend contract).
Schemas for analytics and evaluation are added on the day their routes are built.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints
from pydantic.alias_generators import to_camel

from app.config import settings

# --- Base classes ---------------------------------------------------------------------------


class CamelModel(BaseModel):
    """Responses: serialised as camelCase; can be built straight from ORM objects."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class RequestModel(CamelModel):
    """Requests: unknown fields are rejected with 422 (e.g. a client-sent `organizationId`)."""

    model_config = ConfigDict(extra="forbid")


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SessionId = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]


# --- Health ---------------------------------------------------------------------------------


class HealthOut(CamelModel):
    status: Literal["ok"] = "ok"
    indexed_chunks: int
    llm_provider: str


# --- Sources --------------------------------------------------------------------------------


class SourceCreate(RequestModel):
    """POST /sources. Only websites here; files go through POST /sources/upload."""

    kind: Literal["website"]
    location: HttpUrl  # http(s) only; the SSRF check runs in the router (Day 2)
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None


class SourceOut(CamelModel):
    id: str
    kind: str
    label: str
    location: str
    status: str
    page_count: int
    chunk_count: int
    last_indexed_at: datetime | None
    error: str | None
    created_at: datetime


# --- Chat -----------------------------------------------------------------------------------


class ChatRequest(RequestModel):
    question: Annotated[NonEmptyStr, Field(max_length=settings.max_question_chars)]
    session_id: SessionId


class Citation(CamelModel):
    chunk_id: str
    source_label: str
    heading_path: str
    similarity: float
    excerpt: str


class ChatResponse(CamelModel):
    id: str
    role: Literal["assistant"] = "assistant"
    text: str
    created_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    low_confidence: bool
    citations: list[Citation] = Field(default_factory=list, max_length=5)
