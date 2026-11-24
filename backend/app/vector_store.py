"""Chroma adapter (SPEC section 5.6). The ONLY module that imports chromadb.

Adapter pattern: the rest of the app calls upsert / search / delete_source / count and never
sees Chroma's API, so swapping to pgvector or Qdrant later means rewriting just this file.

Tenancy: every record carries `organization_id` in its metadata, and every search and delete
filters on it. Distance -> similarity is converted here and nowhere else.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.config import settings

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection

_collection: Collection | None = None
_lock = threading.Lock()


@dataclass(frozen=True)
class VectorRecord:
    chunk_id: str
    vector: list[float]
    text: str
    organization_id: str
    source_id: str
    source_label: str
    heading_path: str
    url: str | None


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    similarity: float  # 0..1, higher = closer
    text: str
    source_id: str
    source_label: str
    heading_path: str
    url: str | None


def _get_collection() -> Collection:
    global _collection
    if _collection is None:
        with _lock:
            if _collection is None:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                chroma_settings = ChromaSettings(anonymized_telemetry=False)
                if settings.chroma_path == ":memory:":
                    client = chromadb.EphemeralClient(settings=chroma_settings)
                else:
                    client = chromadb.PersistentClient(
                        path=settings.chroma_path, settings=chroma_settings
                    )
                # Cosine distance on HNSW: distance = 1 - cosine similarity.
                _collection = client.get_or_create_collection(
                    name=settings.chroma_collection, metadata={"hnsw:space": "cosine"}
                )
    return _collection


def _similarity(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - float(distance)))


def upsert(records: list[VectorRecord]) -> None:
    if not records:
        return
    _get_collection().upsert(
        ids=[r.chunk_id for r in records],
        embeddings=[r.vector for r in records],
        documents=[r.text for r in records],
        metadatas=[
            {
                "organization_id": r.organization_id,
                "source_id": r.source_id,
                "source_label": r.source_label,
                "heading_path": r.heading_path,
                "url": r.url or "",  # Chroma metadata can't hold None
            }
            for r in records
        ],
    )


def search(vector: list[float], top_k: int, org: str) -> list[Hit]:
    """The `top_k` chunks closest to `vector`, from this organization only, closest first."""
    result: Any = _get_collection().query(
        query_embeddings=[vector],
        n_results=top_k,
        where={"organization_id": org},
        include=["documents", "metadatas", "distances"],
    )
    ids, docs = result["ids"][0], result["documents"][0]
    metas, distances = result["metadatas"][0], result["distances"][0]
    return [
        Hit(
            chunk_id=chunk_id,
            similarity=_similarity(distance),
            text=doc or "",
            source_id=str(meta["source_id"]),
            source_label=str(meta["source_label"]),
            heading_path=str(meta["heading_path"]),
            url=str(meta["url"]) or None,
        )
        for chunk_id, doc, meta, distance in zip(ids, docs, metas, distances, strict=True)
    ]


def delete_source(source_id: str, org: str) -> None:
    """Remove all vectors of one source. The org filter means a wrong ID can't touch other tenants."""
    _get_collection().delete(
        where={"$and": [{"source_id": source_id}, {"organization_id": org}]}
    )


def count() -> int:
    return _get_collection().count()


def reset_for_tests() -> None:
    """Drop every vector. Only for the in-memory store used by the test suite."""
    if settings.chroma_path != ":memory:":
        raise RuntimeError("reset_for_tests() refuses to wipe a persistent vector store")
    collection = _get_collection()
    existing = collection.get(include=[])["ids"]
    if existing:
        collection.delete(ids=existing)
