"""Ingestion pipeline (SPEC section 5.7): source -> pages/text -> chunks -> SQL + vectors.

Runs as a background task after the request has returned, so it opens its OWN DB session
(the request's session from get_db is already closed by then) and never raises.

Status: queued -> crawling -> indexing -> ready, or failed with an error message.
Re-indexing replaces the old chunks; it never appends duplicates.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import embeddings
from app.config import settings
from app.db import SessionLocal
from app.ingest import chunker, crawler
from app.models import Chunk, Source, new_id

logger = logging.getLogger(__name__)


class IngestError(Exception):
    """A failure whose message is safe to show the customer."""


@dataclass(frozen=True)
class Extracted:
    chunks: list[chunker.RawChunk]
    page_count: int


def upload_path(source: Source) -> Path:
    """Uploads are stored as `<source id><ext>`: a random name, never the user's file name."""
    return Path(settings.upload_dir) / f"{source.id}{Path(source.location).suffix.lower()}"


def content_hash(texts: list[str]) -> str:
    """First 16 hex chars of SHA-256 over all chunk texts: tells us if a re-index changed anything."""
    return hashlib.sha256("\n".join(texts).encode()).hexdigest()[:16]


def _set_status(db: Session, source: Source, status: str) -> None:
    source.status = status
    db.commit()


def _extract(db: Session, source: Source) -> Extracted:
    if source.kind == "website":
        _set_status(db, source, "crawling")
        try:
            pages = crawler.crawl(source.location)
        except crawler.CrawlError as exc:
            raise IngestError(str(exc)) from exc
        chunks = [
            chunk
            for page in pages
            for chunk in chunker.chunk_sections(chunker.sections_from_html(page.html), url=page.url)
        ]
        return Extracted(chunks=dedupe(chunks), page_count=len(pages))

    path = upload_path(source)
    parser = chunker.PARSERS.get(path.suffix)
    if parser is None or not path.is_file():
        raise IngestError("uploaded file is missing or has an unsupported type")
    text = parser(path.read_bytes())
    chunks = chunker.chunk_sections(chunker.sections_from_plain(text, source.label))
    return Extracted(chunks=dedupe(chunks), page_count=1)


def dedupe(chunks: list[chunker.RawChunk]) -> list[chunker.RawChunk]:
    """Keep the first copy of each chunk text (ignoring case and spacing).

    Sites repeat the same blurbs on many index pages. Duplicates would fill several of the
    top-k retrieval slots with one passage and inflate confidence.
    """
    seen: set[str] = set()
    unique: list[chunker.RawChunk] = []
    for chunk in chunks:
        key = " ".join(chunk.text.lower().split())
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique


def _index(db: Session, source: Source, extracted: Extracted) -> None:
    _set_status(db, source, "indexing")
    if not extracted.chunks:
        raise IngestError("no readable text found")

    texts = [c.text for c in extracted.chunks]
    vectors = embeddings.embed(texts)

    # Replace, not append: remove this source's old chunks (and their vectors: same rows) first.
    db.execute(
        delete(Chunk).where(Chunk.source_id == source.id, Chunk.organization_id == source.organization_id)
    )
    rows = [
        Chunk(
            id=new_id("chk"),
            organization_id=source.organization_id,
            source_id=source.id,
            heading_path=c.heading_path,
            url=c.url,
            text=c.text,
            word_count=c.word_count,
            embedding=vector,
        )
        for c, vector in zip(extracted.chunks, vectors, strict=True)
    ]
    db.add_all(rows)

    source.page_count = extracted.page_count
    source.chunk_count = len(rows)
    source.content_hash = content_hash(texts)
    source.last_indexed_at = datetime.now(timezone.utc)
    source.error = None
    source.status = "ready"
    db.commit()  # rows, vectors and the "ready" status: one transaction, all or nothing


def run_ingestion(source_id: str, org: str) -> None:
    """Background task entry point. Never raises: failures end as status `failed`."""
    with SessionLocal() as db:
        source = db.scalar(
            select(Source).where(Source.id == source_id, Source.organization_id == org)
        )
        if source is None:
            logger.warning("ingestion: source %s not found for org %s", source_id, org)
            return

        try:
            _index(db, source, _extract(db, source))
            logger.info("ingested %s: %d chunks", source.id, source.chunk_count)
        except Exception as exc:
            db.rollback()  # undoes the new rows AND their vectors: they're the same rows
            if isinstance(exc, IngestError):
                message = str(exc)
            else:
                logger.exception("ingestion failed for %s", source.id)
                message = "indexing failed because of an internal error"  # don't leak internals
            db.execute(delete(Chunk).where(Chunk.source_id == source.id, Chunk.organization_id == org))
            source.status, source.error = "failed", message[:500]
            source.chunk_count = 0
            db.commit()
