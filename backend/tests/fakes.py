"""Test doubles. FakeEmbedder replaces the 90 MB model: deterministic, instant, offline."""

from __future__ import annotations

import hashlib
import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

FAKE_DIMENSION = 384  # the schema's vector(384): the same tests also run on Postgres


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Bag of words hashed into 384 buckets, L2-normalised.

    Not semantic, but texts that share words get similar vectors, which is enough to test
    ranking, filtering and the distance -> similarity conversion.
    """
    vectors = []
    for text in texts:
        vector = [0.0] * FAKE_DIMENSION
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % FAKE_DIMENSION
            vector[bucket] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        vectors.append([x / norm for x in vector])
    return vectors


def add_chunk(
    db: Session, chunk_id: str, text: str, org: str, *, source_id: str | None = None,
    heading: str = "Billing › Refunds", label: str = "Docs",
) -> None:
    """Insert a chunk (and its source if new) with a fake embedding, like ingestion would."""
    from app.models import Chunk, Source  # app imports stay below conftest's env setup

    source_id = source_id or f"src_{org}"
    if db.get(Source, source_id) is None:
        db.add(Source(id=source_id, organization_id=org, kind="website", label=label, location="https://docs.test"))
    db.add(Chunk(id=chunk_id, organization_id=org, source_id=source_id, heading_path=heading,
                 text=text, word_count=len(text.split()), embedding=fake_embed([text])[0]))  # fmt: skip
    db.commit()
