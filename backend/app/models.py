"""ORM models: the 9 tables from SPEC section 3.

Every table has a non-null `organization_id`, indexed as the leading column of a composite
index, and every query must filter by it.
IDs look like `<prefix>_<12 hex>`, e.g. `src_ab12cd34ef56`.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base


def new_id(prefix: str) -> str:
    """`src_ab12cd34ef56`: a type prefix plus 12 random hex characters (48 bits)."""
    return f"{prefix}_{secrets.token_hex(6)}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores datetimes in UTC and always returns them timezone-aware.

    SQLite has no timezone support and returns naive datetimes; Postgres returns aware ones.
    This type makes both behave the same, and rejects naive datetimes on write.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: use datetime.now(timezone.utc)")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


def _org_column() -> Mapped[str]:
    # No single-column index: every table has a composite index that starts with
    # organization_id, which already serves org-only lookups (leftmost-prefix rule).
    return mapped_column(String(64), nullable=False)


# --- Knowledge base -------------------------------------------------------------------------


class Source(Base):
    """A connected doc source: a crawled website or an uploaded file."""

    __tablename__ = "sources"
    __table_args__ = (Index("ix_sources_org_created_at", "organization_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("src"))
    organization_id: Mapped[str] = _org_column()
    kind: Mapped[str] = mapped_column(String(16))  # website | pdf | docx | text
    label: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(Text)  # URL or original file name
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|crawling|indexing|ready|failed
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    last_indexed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="source", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    """One retrievable passage of a source. Its embedding lives in Chroma under the same id."""

    __tablename__ = "chunks"
    __table_args__ = (Index("ix_chunks_org_source_id", "organization_id", "source_id"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("chk"))
    organization_id: Mapped[str] = _org_column()
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    heading_path: Mapped[str] = mapped_column(Text, default="")  # e.g. "Billing › Refunds"
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[Source] = relationship(back_populates="chunks")


# --- Chat log -------------------------------------------------------------------------------


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_org_session_id", "organization_id", "session_id"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("conv"))
    organization_id: Mapped[str] = _org_column()
    session_id: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    synthetic: Mapped[bool] = mapped_column(default=False)  # True for seeded demo traffic

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_org_period", "organization_id", "period"),
        Index("ix_messages_org_created_at", "organization_id", "created_at"),
        Index("ix_messages_org_conversation_id", "organization_id", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("msg"))
    organization_id: Mapped[str] = _org_column()
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # customer | assistant
    text: Mapped[str] = mapped_column(Text)
    # Retrieval-based confidence, computed before generation (SPEC section 6).
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieved_chunk_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    retrieved_scores: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    period: Mapped[str] = mapped_column(String(7))  # "YYYY-MM", set on write; required

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


# --- Analytics (written by the monthly batch, SPEC section 7) -------------------------------


class TopicCluster(Base):
    """One topic found in one period's customer questions."""

    __tablename__ = "topic_clusters"
    __table_args__ = (Index("ix_topic_clusters_org_period", "organization_id", "period"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("ins"))
    organization_id: Mapped[str] = _org_column()
    period: Mapped[str] = mapped_column(String(7))  # "YYYY-MM"
    rank: Mapped[int] = mapped_column(Integer, default=0)  # 1 = highest priority
    name: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    query_count: Mapped[int] = mapped_column(Integer, default=0)
    previous_query_count: Mapped[int] = mapped_column(Integer, default=0)
    growth: Mapped[float] = mapped_column(Float, default=0.0)
    mean_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[float] = mapped_column(Float, default=0.0)
    severity_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[float] = mapped_column(Float, default=0.0)
    trend: Mapped[str] = mapped_column(String(16))  # baseline|emerging|recurring|stable|declining
    centroid: Mapped[list[float]] = mapped_column(JSON, default=list)
    # Plain column, not a FK: re-running an earlier period deletes and rebuilds its clusters,
    # and a FK would break (or cascade into) the later period's links.
    previous_cluster_id: Mapped[str | None] = mapped_column(String(24), nullable=True)

    members: Mapped[list[ClusterMember]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan", passive_deletes=True
    )


class ClusterMember(Base):
    """Link table: which customer messages belong to which topic cluster."""

    __tablename__ = "cluster_members"
    __table_args__ = (Index("ix_cluster_members_org_cluster_id", "organization_id", "cluster_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = _org_column()
    cluster_id: Mapped[str] = mapped_column(
        ForeignKey("topic_clusters.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)

    cluster: Mapped[TopicCluster] = relationship(back_populates="members")


class Report(Base):
    """The monthly summary for one period."""

    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_org_period", "organization_id", "period"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("rep"))
    organization_id: Mapped[str] = _org_column()
    period: Mapped[str] = mapped_column(String(7))
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    conversation_count: Mapped[int] = mapped_column(Integer, default=0)
    query_count: Mapped[int] = mapped_column(Integer, default=0)
    unanswered_rate: Mapped[float] = mapped_column(Float, default=0.0)  # share with low confidence
    summary: Mapped[str] = mapped_column(Text, default="")

    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )


class Recommendation(Base):
    """A concrete action for one of the report's top topics."""

    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendations_org_report_id", "organization_id", "report_id"),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("rec"))
    organization_id: Mapped[str] = _org_column()
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    # Copied, not a FK, so the recommendation still reads correctly if clusters are rebuilt.
    cluster_id: Mapped[str] = mapped_column(String(24))
    cluster_name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(24))  # product|documentation|faq|customer_issue
    headline: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    faq_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_queries: Mapped[list[str]] = mapped_column(JSON, default=list)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    growth: Mapped[float] = mapped_column(Float, default=0.0)
    expected_effect: Mapped[str] = mapped_column(Text, default="")

    report: Mapped[Report] = relationship(back_populates="recommendations")


# --- Evaluation (SPEC section 8) ------------------------------------------------------------


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (Index("ix_evaluation_runs_org_ran_at", "organization_id", "ran_at"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: new_id("eval"))
    organization_id: Mapped[str] = _org_column()
    ran_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    # Judge calls that failed are left out of the averages, not counted as 0 (SPEC section 9 #9).
    failed_judgements: Mapped[int] = mapped_column(Integer, default=0)
    # None when every judgement for that metric failed.
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    failures: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
