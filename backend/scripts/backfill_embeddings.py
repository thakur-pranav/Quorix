"""Fill chunks.embedding for rows that don't have one (after the pgvector migration).

The chunk text is already in the database and embedding is deterministic, so re-embedding the
text gives the same vectors Chroma held: nothing needs to be read from Chroma. Idempotent: only
NULL rows are touched, in batches, each batch committed. Usage (from backend/):
    alembic upgrade head
    python -m scripts.backfill_embeddings
"""

from __future__ import annotations

from sqlalchemy import select

from app import embeddings
from app.config import settings
from app.db import SessionLocal
from app.models import Chunk

BATCH = 256


def main() -> None:
    if embeddings.dimension() != settings.embedding_dimension:
        raise SystemExit("the model's dimension doesn't match EMBEDDING_DIMENSION: see app/main.py")
    done = 0
    with SessionLocal() as db:
        while True:
            # All orgs on purpose: this is an operator script, not a request (no tenant to scope to).
            batch = list(db.scalars(select(Chunk).where(Chunk.embedding.is_(None)).order_by(Chunk.id).limit(BATCH)))
            if not batch:
                break
            for chunk, vector in zip(batch, embeddings.embed([c.text for c in batch]), strict=True):
                chunk.embedding = vector
            db.commit()
            done += len(batch)
            print(f"embedded {done} chunks")
    print(f"done: {done} chunks backfilled")


if __name__ == "__main__":
    main()
