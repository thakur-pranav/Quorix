"""Similarity search on chunks.embedding: ranking, tenant isolation, cascade deletes."""

from __future__ import annotations

import math

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import embeddings, vector_store
from app.models import Chunk, Source
from tests.fakes import add_chunk


def test_search_returns_closest_first_with_similarity(db: Session) -> None:
    add_chunk(db, "chk_a", "refunds take five business days", "org_a")
    add_chunk(db, "chk_b", "reset your password from settings", "org_a")
    hits = vector_store.search(db, embeddings.embed_one("how many days do refunds take"), 5, "org_a")
    assert [h.chunk_id for h in hits] == ["chk_a", "chk_b"]
    assert 0.0 <= hits[1].similarity < hits[0].similarity <= 1.0
    assert hits[0].heading_path == "Billing › Refunds" and hits[0].url is None
    assert hits[0].source_label == "Docs"  # joined from the source row


def test_top_k_limits_the_results(db: Session) -> None:
    for n in range(4):
        add_chunk(db, f"chk_{n}", f"refund policy number {n}", "org_a")
    assert len(vector_store.search(db, embeddings.embed_one("refund"), 2, "org_a")) == 2


def test_one_org_never_sees_another_orgs_chunks(db: Session) -> None:
    """ROADMAP Day 2 test: tenant isolation in the vector search."""
    add_chunk(db, "chk_mine", "refunds take five business days", "org_a")
    add_chunk(db, "chk_theirs", "refunds take five business days", "org_b")  # identical text
    query = embeddings.embed_one("refunds take five business days")
    assert [h.chunk_id for h in vector_store.search(db, query, 5, "org_a")] == ["chk_mine"]
    assert [h.chunk_id for h in vector_store.search(db, query, 5, "org_b")] == ["chk_theirs"]
    assert vector_store.search(db, query, 5, "org_nobody") == []


def test_deleting_a_source_deletes_its_vectors_in_the_same_transaction(db: Session) -> None:
    """The point of pgvector here: vectors are columns, so the FK cascade removes them too."""
    add_chunk(db, "chk_1", "alpha text", "org_a", source_id="src_1")
    add_chunk(db, "chk_2", "beta text", "org_a", source_id="src_2")
    add_chunk(db, "chk_3", "alpha text", "org_b", source_id="src_3")
    db.delete(db.get(Source, "src_1"))
    db.commit()

    query = embeddings.embed_one("text")
    assert {h.chunk_id for h in vector_store.search(db, query, 5, "org_a")} == {"chk_2"}
    assert {h.chunk_id for h in vector_store.search(db, query, 5, "org_b")} == {"chk_3"}  # untouched
    assert vector_store.count(db, "org_a") == 1


def test_chunks_without_an_embedding_are_skipped(db: Session) -> None:
    """Rows waiting for the backfill must not break search or appear in it."""
    add_chunk(db, "chk_1", "refunds", "org_a")
    db.add(Chunk(id="chk_2", organization_id="org_a", source_id="src_org_a", text="refunds", embedding=None))
    db.commit()
    assert [h.chunk_id for h in vector_store.search(db, embeddings.embed_one("refunds"), 5, "org_a")] == ["chk_1"]
    assert vector_store.count(db, "org_a") == 1
    assert len(db.scalars(select(Chunk)).all()) == 2


@pytest.mark.parametrize(("distance", "similarity"), [(0.0, 1.0), (0.25, 0.75), (1.0, 0.0), (1.6, 0.0)])
def test_distance_to_similarity_is_clamped(distance: float, similarity: float) -> None:
    assert vector_store.similarity_from_distance(distance) == pytest.approx(similarity)


@pytest.mark.real_model
@pytest.mark.skipif("not config.getoption('--real-model')", reason="needs --real-model (downloads 90 MB)")
def test_real_model_dimension_and_normalisation() -> None:
    from app.config import settings

    vectors = embeddings.embed(["How do refunds work?", "Refund policy"])
    assert len(vectors[0]) == embeddings.dimension() == settings.embedding_dimension
    assert math.isclose(math.sqrt(sum(x * x for x in vectors[0])), 1.0, rel_tol=1e-4)
