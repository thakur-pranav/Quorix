from __future__ import annotations

import pytest

from app.analytics.trends import classify_trend, compute_growth, cosine, priority


def test_priority_matches_the_spec_example() -> None:
    """SPEC 7.10: count 9, max 20, growth 1.25, confidence 0.35, severity 0.55 → 0.505."""
    assert priority(9, 20, 1.25, 0.35, 0.55) == pytest.approx(0.505)


def test_priority_squashes_growth_and_clamps() -> None:
    assert priority(20, 20, 3.0, 0.0, 1.0) == 1.0  # everything maxed
    assert priority(20, 20, 30.0, 0.0, 1.0) == 1.0  # growth beyond 300% adds nothing more
    assert priority(1, 20, -0.9, 1.0, 0.0) == pytest.approx(0.015)  # shrinking growth counts as 0


@pytest.mark.parametrize(
    ("current", "previous", "has_previous_period", "expected"),
    [
        (30, 0, False, "baseline"),  # first period: nothing to compare with (the zip said "emerging")
        (12, 0, True, "emerging"),  # new topic, already a real cluster
        (40, 15, True, "emerging"),  # growth 1.67 from a small base (≤ 25)
        (60, 30, True, "recurring"),  # doubled, but the base was too big to call it emerging
        (25, 30, True, "recurring"),  # ≥ 70% of last time
        (18, 30, True, "stable"),  # between 50% and 70%
        (14, 30, True, "declining"),  # under half of last time (the zip had no such state)
    ],
)
def test_classify_trend_covers_every_state(current: int, previous: int, has_previous_period: bool, expected: str) -> None:
    growth = compute_growth(current, previous)
    assert classify_trend(current, previous, growth, has_previous_period=has_previous_period) == expected


def test_planted_growing_topic_is_emerging_then_recurring() -> None:
    """The seed plan: 5 → 15 → 40. 5 → 15 is +200% from a small base; 15 → 40 is +167%, still emerging."""
    assert classify_trend(15, 5, compute_growth(15, 5), has_previous_period=True) == "emerging"
    assert classify_trend(40, 15, compute_growth(40, 15), has_previous_period=True) == "emerging"


def test_growth() -> None:
    assert compute_growth(15, 10) == 0.5
    assert compute_growth(5, 10) == -0.5
    assert compute_growth(7, 0) == 7.0  # new topic: its whole volume


def test_cosine() -> None:
    assert cosine([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)  # direction, not length
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0  # no division by zero
