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


# --- Analytics (SPEC sections 4 and 7) ------------------------------------------------------

class TopicOut(CamelModel):
    id: str
    period: str
    rank: int
    name: str
    keywords: list[str]
    query_count: int
    previous_query_count: int
    growth: float
    mean_confidence: float
    severity: float
    severity_reason: str | None
    priority: float
    trend: str


class TopicHistoryPoint(CamelModel):
    period: str
    query_count: int
    mean_confidence: float
    trend: str


class MemberQuery(CamelModel):
    message_id: str
    text: str
    confidence: float | None
    created_at: datetime


class WeakChunk(CamelModel):
    """A doc passage this topic's questions keep landing on, and how well it matched them."""

    chunk_id: str
    source_label: str
    heading_path: str
    url: str | None
    excerpt: str
    times_retrieved: int
    mean_similarity: float


class TopicDetailOut(TopicOut):
    history: list[TopicHistoryPoint]
    member_queries: list[MemberQuery]
    weakest_chunks: list[WeakChunk]


class RecommendationOut(CamelModel):
    id: str
    cluster_id: str
    cluster_name: str
    category: str
    headline: str
    body: str
    faq_answer: str | None
    supporting_queries: list[str]
    volume: int
    growth: float
    expected_effect: str


class ReportSummaryOut(CamelModel):
    id: str
    period: str
    generated_at: datetime
    conversation_count: int
    query_count: int
    unanswered_rate: float


class ReportOut(ReportSummaryOut):
    summary: str
    recommendations: list[RecommendationOut]


class PeriodVolume(CamelModel):
    period: str
    query_count: int
    mean_confidence: float


class ConfidenceBin(CamelModel):
    start: float  # the bin covers [start, start + width)
    count: int


class OverviewOut(CamelModel):
    period: str | None
    conversation_count: int
    query_count: int
    topic_count: int
    unanswered_rate: float
    mean_confidence: float
    emerging_count: int
    volume_by_period: list[PeriodVolume]
    # The latest month's questions by retrieval confidence, plus the live threshold, so the
    # page draws the "refused below this" line from the backend's real setting.
    confidence_histogram: list[ConfidenceBin]
    low_confidence_threshold: float


# --- Evaluation (SPEC sections 4 and 8) -----------------------------------------------------


class EvaluationFailure(CamelModel):
    question: str
    metric: Literal["faithfulness", "answer_relevance", "context_relevance"]
    score: float
    reason: str
    confidence: float
    answer: str


class EvaluationOut(CamelModel):
    id: str
    ran_at: datetime
    question_count: int
    failed_judgements: int
    faithfulness: float | None  # None when every judgement for the metric failed
    answer_relevance: float | None
    context_relevance: float | None
    failures: list[EvaluationFailure]


class AnalyticsRunRequest(RequestModel):
    """No options: the run always re-analyses the whole window, since topics span all its months.

    An empty model still earns its place: unknown fields (like the old `period`) are a 422.
    """


class AnalyticsRunOut(CamelModel):
    status: Literal["queued"] = "queued"
    periods: list[str]
