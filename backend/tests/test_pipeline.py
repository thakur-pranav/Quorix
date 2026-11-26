from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import embeddings, vector_store
from app.config import settings
from app.ingest import crawler, pipeline
from app.ingest.crawler import CrawlError, Page
from app.models import Chunk, Source

ARTICLE = " ".join(f"refund{i}" for i in range(30))


def fake_pages(_url: str) -> list[Page]:
    return [
        Page("https://docs.example.com/", "Home", f"<h1>Billing</h1><p>{ARTICLE}</p>"),
        Page("https://docs.example.com/faq", "FAQ", f"<h2>Passwords</h2><p>{ARTICLE} reset</p>"),
    ]


@pytest.fixture
def website(db: Session, monkeypatch: pytest.MonkeyPatch) -> Source:
    monkeypatch.setattr(crawler, "crawl", fake_pages)
    source = Source(organization_id="org_a", kind="website", label="Docs", location="https://docs.example.com/")
    db.add(source)
    db.commit()
    return source


def _reload(db: Session, source: Source) -> Source:
    db.expire_all()
    loaded = db.get(Source, source.id)
    assert loaded is not None
    return loaded


def test_website_ingestion_ends_ready_with_counts(db: Session, website: Source) -> None:
    pipeline.run_ingestion(website.id, "org_a")

    source = _reload(db, website)
    assert source.status == "ready" and source.error is None
    assert source.page_count == 2 and source.chunk_count == 2
    assert source.content_hash is not None and re.fullmatch(r"[0-9a-f]{16}", source.content_hash)
    assert source.last_indexed_at is not None

    chunks = db.scalars(select(Chunk).order_by(Chunk.heading_path)).all()
    assert [c.heading_path for c in chunks] == ["Billing", "Passwords"]
    assert {c.organization_id for c in chunks} == {"org_a"}
    assert chunks[0].url == "https://docs.example.com/"

    hits = vector_store.search(db, embeddings.embed_one("refund0 reset"), 5, "org_a")
    assert {h.chunk_id for h in hits} == {c.id for c in chunks}  # every row was written with its vector


def test_reindex_replaces_instead_of_appending(db: Session, website: Source) -> None:
    pipeline.run_ingestion(website.id, "org_a")
    pipeline.run_ingestion(website.id, "org_a")

    assert len(db.scalars(select(Chunk)).all()) == 2
    assert vector_store.count(db, "org_a") == 2


def test_crawl_error_marks_failed_with_message(
    db: Session, website: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_url: str) -> list[Page]:
        raise CrawlError("robots.txt is unreachable or disallows crawling")

    monkeypatch.setattr(crawler, "crawl", refuse)
    pipeline.run_ingestion(website.id, "org_a")

    source = _reload(db, website)
    assert source.status == "failed"
    assert source.error == "robots.txt is unreachable or disallows crawling"


def test_internal_error_is_not_leaked_and_leaves_no_vectors(
    db: Session, website: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline.run_ingestion(website.id, "org_a")  # a good first index

    def broken(_texts: list[str]) -> str:
        raise RuntimeError("disk I/O error at /var/lib/secret/path")

    # Fails after the new rows (with their vectors) were added, before the commit.
    monkeypatch.setattr(pipeline, "content_hash", broken)
    pipeline.run_ingestion(website.id, "org_a")  # the re-index fails half way

    source = _reload(db, website)
    assert source.status == "failed"
    assert source.error == "indexing failed because of an internal error"  # no path leaked
    assert source.chunk_count == 0
    assert db.scalars(select(Chunk)).all() == []  # rows and vectors are the same rows: both gone
    assert vector_store.count(db, "org_a") == 0


def test_page_without_text_fails_cleanly(
    db: Session, website: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crawler, "crawl", lambda _url: [Page("https://docs.example.com/", "", "<p>Hi</p>")])
    pipeline.run_ingestion(website.id, "org_a")
    assert _reload(db, website).error == "no readable text found"


def test_uploaded_text_file_is_ingested(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    source = Source(organization_id="org_a", kind="text", label="notes.md", location="notes.md")
    db.add(source)
    db.commit()
    pipeline.upload_path(source).write_text(f"{ARTICLE}\n\n{ARTICLE} more", encoding="utf-8")

    pipeline.run_ingestion(source.id, "org_a")

    loaded = _reload(db, source)
    assert loaded.status == "ready" and loaded.page_count == 1
    chunk = db.scalars(select(Chunk)).one()  # two short blocks with the same path: merged
    assert chunk.heading_path == "notes.md"


def test_wrong_org_does_nothing(db: Session, website: Source) -> None:
    pipeline.run_ingestion(website.id, "org_b")
    assert _reload(db, website).status == "queued"


def test_duplicate_blurbs_across_pages_are_indexed_once(
    db: Session, website: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    blurb = "Learn what you will be charged for and when charges occur on your monthly bill."
    monkeypatch.setattr(
        crawler,
        "crawl",
        lambda _url: [
            Page("https://docs.example.com/", "Home", f"<h2>Billing</h2><p>{blurb}</p>"),
            Page("https://docs.example.com/a", "A", f"<h2>Overview</h2><p>{blurb.upper()}</p>"),
            Page("https://docs.example.com/b", "B", f"<h2>Plans</h2><p>{ARTICLE}</p>"),
        ],
    )
    pipeline.run_ingestion(website.id, "org_a")
    assert _reload(db, website).chunk_count == 2  # the blurb (any case) once, plus the article
