from __future__ import annotations

from scripts.measure_threshold import Row, best_threshold


def rows(covered: list[float], off: list[float]) -> list[Row]:
    return [Row("q", True, c, c, "") for c in covered] + [Row("q", False, c, c, "") for c in off]


def test_clean_separation_picks_the_middle_of_the_gap() -> None:
    threshold, correct = best_threshold(rows(covered=[0.6, 0.7, 0.8], off=[0.2, 0.3]))
    assert threshold == 0.45  # midway between 0.3 and 0.6
    assert correct == 5


def test_overlap_maximises_correct_calls() -> None:
    # One off-topic question (0.55) scores above one covered question (0.5).
    threshold, correct = best_threshold(rows(covered=[0.5, 0.7, 0.8], off=[0.2, 0.55]))
    assert correct == 4
    assert 0.2 < threshold <= 0.7
