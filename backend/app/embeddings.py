"""Sentence embeddings (SPEC section 5.5): all-MiniLM-L6-v2, run locally, lazy-loaded.

Text -> a vector of floats where similar meaning means a similar direction. Vectors are
L2-normalised (length 1), so cosine similarity is just the dot product.

Call through the module (`embeddings.embed(...)`), so tests can swap in a fake embedder.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    """Load the model once, on first use, even if many threads ask at the same moment.

    Double-checked locking: the first check skips the lock on the fast path (model already
    loaded); the second check, inside the lock, stops two threads that both saw `None`
    from loading it twice.
    """
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer  # heavy import: on demand

                _model = SentenceTransformer(settings.embedding_model)
    return _model


def dimension() -> int:
    """Vector size, read from the model (384 for MiniLM), never hard-coded (SPEC section 9 #5)."""
    size = _get_model().get_embedding_dimension()  # renamed in sentence-transformers 6
    if size is None:
        raise RuntimeError(f"{settings.embedding_model} does not report an embedding dimension")
    return int(size)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed many texts in batches. Output vectors have length 1."""
    if not texts:
        return []
    vectors = _get_model().encode(
        texts,
        batch_size=settings.embedding_batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [[float(x) for x in row] for row in vectors]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
