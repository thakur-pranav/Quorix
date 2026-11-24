"""Test doubles. FakeEmbedder replaces the 90 MB model: deterministic, instant, offline."""

from __future__ import annotations

import hashlib
import math
import re

FAKE_DIMENSION = 64


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Bag of words hashed into 64 buckets, L2-normalised.

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
