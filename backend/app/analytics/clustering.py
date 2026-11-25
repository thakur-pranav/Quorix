"""Topic discovery (SPEC sections 7.1 to 7.5): embeddings → UMAP → HDBSCAN → keywords → names.

Why this pipeline:
- 384-dimensional embeddings suffer from the curse of dimensionality: distances become similar,
  so density-based clustering struggles. UMAP reduces to 5 dimensions while keeping neighbours
  close (it's non-linear, unlike PCA, and keeps more global structure than t-SNE).
- HDBSCAN finds clusters of any shape and number, and labels one-off questions as noise (-1),
  where k-means would force every question into one of k clusters you had to guess in advance.
"""

from __future__ import annotations

import logging
import math
import re
import warnings
from collections import Counter
from dataclasses import dataclass

import numpy as np

from app import llm
from app.config import settings

logger = logging.getLogger(__name__)

STOP_WORDS = frozenset(
    """the and for are was were been being this that these those with from into onto about your
    yours you our ours their they them what when where which who whom why how can could would
    should will shall does did doing done have has had having not but any all some each every
    there here than then too very just also only own same other such more most get gets got
    getting use used using make made want need please thanks thank hello help able way""".split()
)
_TOKEN = re.compile(r"[a-z][a-z0-9'-]+")


@dataclass
class Topic:
    indices: list[int]  # positions in the input lists
    centroid: list[float]  # mean of the members' ORIGINAL (not UMAP) vectors
    keywords: list[str]
    name: str


def tokenize(text: str) -> list[str]:
    """Lowercase words of 3+ letters, stop words removed."""
    return [w for w in _TOKEN.findall(text.lower()) if len(w) >= 3 and w not in STOP_WORDS]


def class_tfidf(docs_by_topic: dict[int, list[str]], top_n: int) -> dict[int, list[str]]:
    """c-TF-IDF: treat each topic as ONE document, then find its distinctive words.

    score(term, topic) = tf(term in topic) × log(1 + n_topics / topics_containing_term)
    A word common to every topic ("account") scores low; one concentrated in a topic
    ("declined") scores high. Plain TF-IDF over single questions is too sparse for this.
    """
    counts = {topic: Counter(w for doc in docs for w in tokenize(doc)) for topic, docs in docs_by_topic.items()}
    n_topics = len(counts)
    document_frequency: Counter[str] = Counter(term for c in counts.values() for term in c)
    keywords: dict[int, list[str]] = {}
    for topic, counter in counts.items():
        total = sum(counter.values()) or 1
        scored = {
            term: (count / total) * math.log(1 + n_topics / document_frequency[term])
            for term, count in counter.items()
        }
        keywords[topic] = [t for t, _ in sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]]
    return keywords


NAME_PROMPT = """You name clusters of customer support questions. Reply with a short, specific \
title of at most 8 words describing what customers are trying to do or what is going wrong. \
Plain text only: no quotes, no trailing full stop."""


def name_topic(keywords: list[str], samples: list[str]) -> str:
    """LLM title (≤ 8 words); fallback: the top 3 keywords."""
    fallback = " ".join(keywords[:3]).capitalize() or "Unnamed topic"
    questions = "\n".join(f"- {s}" for s in samples[: settings.topic_name_samples])
    try:
        raw = llm.complete(f"Keywords: {', '.join(keywords)}\nQuestions:\n{questions}", NAME_PROMPT, temperature=0.2, max_tokens=200)
    except llm.LLMError as exc:
        logger.info("topic naming unavailable: %s", exc)
        return fallback
    # Untrusted output: first line, no quotes or markdown, capped length.
    line = raw.strip().splitlines()[0] if raw.strip() else ""
    name = line.strip().strip("\"'*#`").rstrip(".").strip()
    words = name.split()
    if not words:
        return fallback
    return " ".join(words[: settings.topic_name_max_words])[:120]


def reduce_and_cluster(vectors: np.ndarray) -> np.ndarray:
    """UMAP to a few dimensions, then HDBSCAN. Returns one label per row (-1 = noise)."""
    import umap  # heavy imports: only when the batch actually runs
    from sklearn.cluster import HDBSCAN

    n = len(vectors)
    warnings.filterwarnings("ignore", message=".*n_jobs value.*overridden.*")  # fixed seed disables parallelism
    reducer = umap.UMAP(
        n_neighbors=min(settings.umap_neighbours, n - 1),
        n_components=min(settings.umap_components, n - 2),
        metric="cosine",
        min_dist=settings.umap_min_dist,
        random_state=settings.umap_random_state,
        compatibility_layout=settings.umap_compatibility_layout,  # pinned: a future default changes the layout
    )
    reduced = reducer.fit_transform(vectors)
    return HDBSCAN(
        min_cluster_size=settings.hdbscan_min_cluster_size,
        min_samples=settings.hdbscan_min_samples,
        metric="euclidean",
        copy=True,  # never modify the caller's array (the default changes in scikit-learn 1.10)
    ).fit_predict(reduced)


def discover_topics(texts: list[str], vectors: np.ndarray) -> tuple[list[Topic], int]:
    """Cluster questions into topics. Returns (topics, noise_count). Too few questions → none."""
    if len(texts) < 2 * settings.hdbscan_min_cluster_size:
        logger.warning("only %d questions: need at least %d to cluster", len(texts), 2 * settings.hdbscan_min_cluster_size)
        return [], len(texts)

    labels = reduce_and_cluster(vectors)
    groups: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        if label != -1:
            groups.setdefault(int(label), []).append(index)

    keywords = class_tfidf({label: [texts[i] for i in members] for label, members in groups.items()}, settings.topic_keywords)
    topics = [
        Topic(
            indices=members,
            centroid=[float(x) for x in vectors[members].mean(axis=0)],
            keywords=keywords[label],
            name=name_topic(keywords[label], [texts[i] for i in members]),
        )
        for label, members in sorted(groups.items())
    ]
    noise = int((labels == -1).sum())
    logger.info("%d topics from %d questions (%d noise)", len(topics), len(texts), noise)
    return topics, noise
