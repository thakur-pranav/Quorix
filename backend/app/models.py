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
