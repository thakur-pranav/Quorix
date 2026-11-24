from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Chunk, Conversation, Message, Source, new_id

ID_PATTERN = re.compile(r"^[a-z]+_[0-9a-f]{12}$")


def _source(org: str = "org_a") -> Source:
    return Source(organization_id=org, kind="website", label="Docs", location="https://example.com")


def test_new_id_format() -> None:
    assert ID_PATTERN.match(new_id("src"))
    assert new_id("src") != new_id("src")


def test_defaults_ids_and_utc_timestamps(db: Session) -> None:
    src = _source()
    db.add(src)
    db.commit()
    db.expire_all()  # force a real reload from the database

    loaded = db.get(Source, src.id)
    assert loaded is not None
    assert loaded.id.startswith("src_") and ID_PATTERN.match(loaded.id)
    assert loaded.status == "queued"
    assert loaded.created_at.tzinfo is not None  # aware even though SQLite stores naive


def test_naive_datetime_is_rejected(db: Session) -> None:
    src = _source()
    src.last_indexed_at = datetime(2026, 1, 1)  # no tzinfo
    db.add(src)
    with pytest.raises(StatementError):
        db.commit()


def test_deleting_source_cascades_to_chunks(db: Session) -> None:
    src = _source()
    src.chunks = [Chunk(organization_id="org_a", text="hello", word_count=1) for _ in range(3)]
    db.add(src)
    db.commit()

    db.delete(src)
    db.commit()
    assert db.scalars(select(Chunk)).all() == []


def test_chunk_needs_an_existing_source(db: Session) -> None:
    db.add(Chunk(organization_id="org_a", source_id="src_doesnotexist", text="x"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_message_period_is_required(db: Session) -> None:
    conv = Conversation(organization_id="org_a", session_id="s1")
    conv.messages = [Message(organization_id="org_a", role="customer", text="How do refunds work?")]
    db.add(conv)
    with pytest.raises(IntegrityError):
        db.commit()


def test_message_round_trip(db: Session) -> None:
    conv = Conversation(organization_id="org_a", session_id="s1")
    conv.messages = [
        Message(
            organization_id="org_a",
            role="assistant",
            text="Refunds take 5 days.",
            confidence=0.82,
            retrieved_chunk_ids=["chk_000000000001"],
            retrieved_scores=[0.82],
            period="2026-11",
            created_at=datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc),
        )
    ]
    db.add(conv)
    db.commit()
    db.expire_all()

    msg = db.scalars(select(Message)).one()
    assert msg.retrieved_chunk_ids == ["chk_000000000001"]
    assert msg.conversation.session_id == "s1"


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("sources", ["organization_id", "created_at"]),
        ("chunks", ["organization_id", "source_id"]),
        ("conversations", ["organization_id", "session_id"]),
        ("messages", ["organization_id", "period"]),
        ("messages", ["organization_id", "created_at"]),
        ("messages", ["organization_id", "conversation_id"]),
    ],
)
def test_composite_indexes_exist(db: Session, table: str, columns: list[str]) -> None:
    indexes = [ix["column_names"] for ix in inspect(engine).get_indexes(table)]
    assert columns in indexes


def test_every_table_has_a_composite_index_led_by_organization_id(db: Session) -> None:
    """Tenancy rule: every table is filtered by org, so org must lead an index on every table."""
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        indexes = [ix["column_names"] for ix in inspector.get_indexes(table)]
        assert any(len(cols) > 1 and cols[0] == "organization_id" for cols in indexes), table
        assert ["organization_id"] not in indexes, f"{table}: redundant single org index"
