"""Similarity search over chunk embeddings (SPEC section 5.6, Day 6: pgvector instead of Chroma).

Vectors live in `chunks.embedding`, next to the text, so a chunk and its vector are written,
replaced and deleted in ONE transaction: no second datastore to keep in step. This module is
the only place that ranks by similarity; callers get `Hit`s and never see the SQL.

- Postgres: pgvector's `<=>` (cosine distance) in SQL, filtered by organization first. No ANN
  (HNSW) index yet: the org filter narrows to one tenant's chunks via the org index, then an
  exact scan is fast at thousands of rows, and exact means no recall loss. An HNSW index plus a
  WHERE filter can return fewer than k rows (the filter runs after the index search).
- SQLite (tests, local dev): the same query without the distance, ranked in Python with numpy.

Tenancy: every query filters on `organization_id`. Distance → similarity is converted here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, bindparam, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Source


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    similarity: float  # 0..1, higher = closer
    text: str
    source_id: str
    source_label: str
    heading_path: str
    url: str | None


def similarity_from_distance(distance: float) -> float:
    """Cosine distance (0 = same direction, 2 = opposite) → similarity clamped to [0, 1]."""
    return max(0.0, min(1.0, 1.0 - float(distance)))


def _hit(chunk: Chunk, label: str, similarity: float) -> Hit:
    return Hit(chunk.id, similarity, chunk.text, chunk.source_id, label, chunk.heading_path, chunk.url)


def search(db: Session, vector: list[float], top_k: int, org: str) -> list[Hit]:
    """The `top_k` chunks closest to `vector`, from this organization only, closest first."""
    base = (
        select(Chunk, Source.label)
        .join(Source, Source.id == Chunk.source_id)
        .where(Chunk.organization_id == org, Chunk.embedding.is_not(None))
    )
    if db.get_bind().dialect.name == "postgresql":
        query = bindparam("query_vector", vector, type_=Vector(settings.embedding_dimension))
        distance = Chunk.embedding.op("<=>", return_type=Float)(query)
        rows = db.execute(base.add_columns(distance).order_by(distance).limit(top_k)).all()
        return [_hit(chunk, label, similarity_from_distance(d)) for chunk, label, d in rows]

    # SQLite: rank in Python. Vectors are unit length, so cosine similarity is the dot product.
    rows = db.execute(base).all()
    if not rows:
        return []
    matrix = np.asarray([chunk.embedding for chunk, _ in rows], dtype=np.float64)
    scores = matrix @ np.asarray(vector, dtype=np.float64)
    best = np.argsort(-scores, kind="stable")[:top_k]
    return [_hit(rows[i][0], rows[i][1], max(0.0, min(1.0, float(scores[i])))) for i in best]


def count(db: Session, org: str) -> int:
    """How many chunks of this organization have an embedding."""
    stmt = select(func.count()).select_from(Chunk).where(Chunk.organization_id == org, Chunk.embedding.is_not(None))
    return db.scalar(stmt) or 0
