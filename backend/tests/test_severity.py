from __future__ import annotations

import pytest

from app import llm
from app.analytics import severity
from app.analytics.severity import rule_severity, score_severity


def test_whole_words_only() -> None:
    """The zip used substring matching: "lost" matched "almost", "error" matched "terror"."""
    assert rule_severity("I almost finished the terror movie").score == 0.35
    assert rule_severity("I lost access after an error").score == pytest.approx(0.55)


def test_hard_terms_raise_and_soft_phrases_lower_the_score() -> None:
    blocked = rule_severity("Payment declined and my account is locked, can't work")
    curious = rule_severity("How do I see invoices? What is the difference between plans?")
    assert blocked.score == pytest.approx(0.35 + 0.10 * 3)  # declined, locked, can't
    assert curious.score == pytest.approx(0.35 - 0.05 * 3)  # how do i, what is, difference between
    assert "declined" in blocked.reason and blocked.source == "rule"


def test_rule_is_clamped() -> None:
    many = " ".join(severity.HARD_TERMS)
    assert rule_severity(many).score == 1.0
    assert rule_severity(" ".join(severity.SOFT_PHRASES) * 3).score == 0.05


@pytest.mark.parametrize(("level", "score"), [(1, 0.1), (2, 0.3), (3, 0.5), (4, 0.75), (5, 0.95)])
def test_llm_level_maps_to_a_configured_score(monkeypatch: pytest.MonkeyPatch, level: int, score: float) -> None:
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: {"level": level, "reason": "Customers are blocked."})
    result = score_severity("Locked out", ["Why is my account locked?"])
    assert (result.score, result.source) == (score, "llm")


def test_prompt_anchors_the_scale_against_inflation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare 0..1 scale made the LLM rate almost every topic 0.8-1.0 (Day 5)."""
    seen: list[str] = []
    monkeypatch.setattr(llm, "complete_json", lambda user, system, **k: seen.append(system) or {"level": 2, "reason": "x"})
    score_severity("Invoices", ["How do I download an invoice?"])
    assert "TYPICAL question" in seen[0] and "Most topics are 2 or 3" in seen[0]


@pytest.mark.parametrize(
    "reply",
    [
        {"level": 6, "reason": "x"},  # out of range
        {"level": 0, "reason": "x"},
        {"level": 3.5, "reason": "x"},  # not a whole level
        {"level": "4", "reason": "x"},  # a string, not a number
        {"level": True, "reason": "x"},  # bool is an int subclass in Python
        {"level": 3, "reason": ""},  # no reason: "why is this ranked high?" needs one
        {"severity": 0.9, "reason": "x"},  # the old format
    ],
)
def test_unusable_llm_output_falls_back_to_the_rule(monkeypatch: pytest.MonkeyPatch, reply: dict[str, object]) -> None:
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: reply)
    assert score_severity("Refunds", ["Where is my refund?"]).source == "rule"


def test_llm_failure_falls_back_to_the_rule() -> None:
    # Tests run with LLM_PROVIDER=none, so the call raises LLMError.
    result = score_severity("Refunds", ["Where is my refund?"])
    assert result.source == "rule" and result.reason.startswith("Keyword rule")
