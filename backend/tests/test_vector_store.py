from __future__ import annotations

import math

import pytest

from app import embeddings, vector_store
from app.vector_store import VectorRecord


def record(chunk_id: str, text: str, org: str, source_id: str = "src_000000000001") -> VectorRecord:
    return VectorRecord(
        chunk_id=chunk_id,
        vector=embeddings.embed_one(text),
        text=text,
        organization_id=org,
        source_id=source_id,
        source_label="Docs",
        heading_path="Billing › Refunds",
        url=None,
    )


def test_search_returns_closest_first_with_similarity() -> None:
    vector_store.upsert(
        [
            record("chk_a", "refunds take five business days", "org_a"),
            record("chk_b", "reset your password from settings", "org_a"),
        ]
    )
    hits = vector_store.search(embeddings.embed_one("how many days do refunds take"), 5, "org_a")
    assert [h.chunk_id for h in hits] == ["chk_a", "chk_b"]
    assert 0.0 <= hits[1].similarity < hits[0].similarity <= 1.0
    assert hits[0].heading_path == "Billing › Refunds" and hits[0].url is None


def test_one_org_never_sees_another_orgs_chunks() -> None:
    """ROADMAP Day 2 test: tenant isolation in the vector store."""
    vector_store.upsert(
        [
            record("chk_mine", "refunds take five business days", "org_a"),
            record("chk_theirs", "refunds take five business days", "org_b"),  # identical text
        ]
    )
    query = embeddings.embed_one("refunds take five business days")
    assert [h.chunk_id for h in vector_store.search(query, 5, "org_a")] == ["chk_mine"]
    assert [h.chunk_id for h in vector_store.search(query, 5, "org_b")] == ["chk_theirs"]
    assert vector_store.search(query, 5, "org_nobody") == []


def test_delete_source_is_scoped_to_source_and_org() -> None:
    vector_store.upsert(
        [
            record("chk_1", "alpha text", "org_a", source_id="src_1"),
            record("chk_2", "beta text", "org_a", source_id="src_2"),
            record("chk_3", "alpha text", "org_b", source_id="src_1"),  # same source id, other org
        ]
    )
    vector_store.delete_source("src_1", "org_a")

    remaining_a = {h.chunk_id for h in vector_store.search(embeddings.embed_one("text"), 5, "org_a")}
    remaining_b = {h.chunk_id for h in vector_store.search(embeddings.embed_one("text"), 5, "org_b")}
    assert remaining_a == {"chk_2"}
    assert remaining_b == {"chk_3"}  # org_b untouched
    assert vector_store.count() == 2


def test_upsert_replaces_by_id() -> None:
    vector_store.upsert([record("chk_1", "old text", "org_a")])
    vector_store.upsert([record("chk_1", "new text", "org_a")])
    assert vector_store.count() == 1
    assert vector_store.search(embeddings.embed_one("new"), 1, "org_a")[0].text == "new text"


@pytest.mark.parametrize(("distance", "similarity"), [(0.0, 1.0), (0.25, 0.75), (1.0, 0.0), (1.6, 0.0)])
def test_distance_to_similarity_is_clamped(distance: float, similarity: float) -> None:
    assert vector_store._similarity(distance) == pytest.approx(similarity)


@pytest.mark.real_model
@pytest.mark.skipif("not config.getoption('--real-model')", reason="needs --real-model (downloads 90 MB)")
def test_real_model_dimension_and_normalisation() -> None:
    vectors = embeddings.embed(["How do refunds work?", "Refund policy"])
    assert len(vectors[0]) == embeddings.dimension() == 384
    assert math.isclose(math.sqrt(sum(x * x for x in vectors[0])), 1.0, rel_tol=1e-4)
