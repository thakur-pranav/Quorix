"""Trends and ranking (SPEC sections 7.8 to 7.10).

No matching step: the batch clusters the whole window once, so a topic's monthly counts are
its own (docs/NOTES.md, Day 5). `cosine` stays for the tuning script's matching experiment.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.config import settings


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    denominator = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb) / denominator if denominator else 0.0


def compute_growth(current: int, previous: int) -> float:
    """(current - previous) / previous; for a brand-new topic, its whole count."""
    if previous == 0:
        return float(current)
    return round((current - previous) / previous, 4)


def classify_trend(current: int, previous: int, growth: float, *, has_previous_period: bool) -> str:
    """SPEC 7.9, checked in order. `baseline` fixes the zip's "every first-month topic is emerging"."""
    if not has_previous_period:
        return "baseline"  # nothing to compare with yet
    if previous == 0 and current >= settings.topic_min_period_questions:
        return "emerging"  # new, and already a real cluster
    if growth >= settings.trend_emerging_growth and previous <= settings.trend_emerging_max_previous:
        return "emerging"  # growing fast from a small base
    if current >= settings.trend_recurring_ratio * previous:
        return "recurring"
    if current < settings.trend_declining_ratio * previous:
        return "declining"
    return "stable"


def priority(count: int, max_count: int, growth: float, mean_confidence: float, severity: float) -> float:
    """0.30·volume + 0.30·growth + 0.25·(1 − confidence) + 0.15·severity, every term in [0, 1].

    Normalise first, then weight: raw counts would swamp everything else. Growth is squashed
    (capped at 300%) so one topic exploding from 1 to 30 can't dominate the whole ranking.
    """
    volume = count / max_count if max_count else 0.0
    growth_term = min(1.0, max(0.0, growth) / settings.priority_growth_cap)
    score = (
        settings.priority_weight_volume * volume
        + settings.priority_weight_growth * growth_term
        + settings.priority_weight_confidence * (1.0 - mean_confidence)
        + settings.priority_weight_severity * severity
    )
    return round(max(0.0, min(1.0, score)), 4)
