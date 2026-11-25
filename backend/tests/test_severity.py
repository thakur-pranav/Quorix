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


def test_llm_score_wins_when_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: {"severity": 0.9, "reason": "Customers are locked out of billing."})
    result = score_severity("Locked out", ["Why is my account locked?"])
    assert (result.score, result.source) == (0.9, "llm")


@pytest.mark.parametrize(
    "reply",
    [{"severity": 1.7, "reason": "x"}, {"severity": "high", "reason": "x"}, {"severity": 0.5, "reason": ""}, {"reason": "no score"}],
)
def test_unusable_llm_output_falls_back_to_the_rule(monkeypatch: pytest.MonkeyPatch, reply: dict[str, object]) -> None:
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: reply)
    assert score_severity("Refunds", ["Where is my refund?"]).source == "rule"


def test_llm_failure_falls_back_to_the_rule() -> None:
    # Tests run with LLM_PROVIDER=none, so the call raises LLMError.
    result = score_severity("Refunds", ["Where is my refund?"])
    assert result.source == "rule" and result.reason.startswith("Keyword rule")
