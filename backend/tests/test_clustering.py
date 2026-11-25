from __future__ import annotations

import numpy as np
import pytest

from app import llm
from app.analytics.clustering import class_tfidf, discover_topics, name_topic, tokenize
from app.config import settings


def test_tokenize_drops_stop_words_and_short_words() -> None:
    assert tokenize("How do I get my REFUND back, please?") == ["refund", "back"]


def test_class_tfidf_prefers_distinctive_words() -> None:
    keywords = class_tfidf(
        {
            0: ["refund my card payment", "card refund delayed", "refund for my card"],
            1: ["reset my card password", "password reset email", "password locked card"],
        },
        top_n=2,
    )
    assert keywords[0][0] == "refund" and keywords[1][0] == "password"
    assert "card" not in keywords[0][:1]  # in every topic, so not distinctive


def test_name_falls_back_to_keywords_without_an_llm() -> None:
    assert name_topic(["refund", "card", "delayed", "bank"], ["q"]) == "Refund card delayed"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"Refund delays on card payments."', "Refund delays on card payments"),
        ("**Card refunds**\nSome extra explanation", "Card refunds"),
        ("one two three four five six seven eight nine ten", "one two three four five six seven eight"),
        ("   ", "Refund card"),  # empty → keyword fallback
    ],
)
def test_llm_names_are_sanitised(monkeypatch: pytest.MonkeyPatch, raw: str, expected: str) -> None:
    monkeypatch.setattr(llm, "complete", lambda *a, **k: raw)
    assert name_topic(["refund", "card"], ["q"]) == expected


def test_discover_topics_finds_separated_groups_and_noise() -> None:
    rng = np.random.default_rng(0)
    centres = rng.normal(size=(3, 32))
    vectors = np.vstack([c + rng.normal(scale=0.05, size=(15, 32)) for c in centres])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    texts = [f"refund money back {i}" for i in range(15)] + [f"password reset login {i}" for i in range(15)] + [
        f"invoice receipt download {i}" for i in range(15)
    ]

    topics, noise = discover_topics(texts, vectors)

    assert len(topics) == 3
    assert sorted(len(t.indices) for t in topics) == [15, 15, 15]
    assert noise == 0
    assert len(topics[0].centroid) == 32  # centroid in the ORIGINAL space, not UMAP's
    for word in ("refund", "password", "invoice"):
        assert sum(word in t.keywords for t in topics) == 1  # each word marks exactly one topic


def test_too_few_questions_means_no_topics() -> None:
    n = 2 * settings.hdbscan_min_cluster_size - 1
    topics, noise = discover_topics(["q"] * n, np.ones((n, 8)))
    assert topics == [] and noise == n
