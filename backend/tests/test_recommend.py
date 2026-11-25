from __future__ import annotations

import pytest

from app import llm
from app.analytics.recommend import TopicFacts, choose_category, write_recommendation


def facts(**overrides: object) -> TopicFacts:
    base: dict[str, object] = dict(
        name="Card declined", keywords=["declined", "card"], query_count=10, growth=0.2,
        trend="recurring", mean_confidence=0.7, severity=0.4, supporting_queries=["Why was my card declined?"],
    )  # fmt: skip
    base.update(overrides)
    return TopicFacts(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "median", "category", "rule"),
    [
        ({"mean_confidence": 0.3, "severity": 0.7, "trend": "emerging"}, 10, "product", "rule 1"),
        ({"mean_confidence": 0.3, "severity": 0.7, "trend": "recurring"}, 10, "documentation", "rule 2"),
        ({"mean_confidence": 0.3}, 10, "documentation", "rule 2"),
        ({"query_count": 12, "severity": 0.4}, 10, "faq", "rule 3"),
        ({"query_count": 5, "severity": 0.8}, 10, "customer_issue", "rule 4"),
        ({"query_count": 8, "severity": 0.58}, 10, "product", "rule 5"),
        ({"query_count": 8, "severity": 0.45}, 10, "faq", "rule 5"),
    ],
)
def test_category_rules_in_order(overrides: dict[str, object], median: float, category: str, rule: str) -> None:
    chosen, why = choose_category(facts(**overrides), median)
    assert chosen == category and why.startswith(rule)


def test_template_used_when_llm_is_down() -> None:
    draft = write_recommendation(facts(mean_confidence=0.3), 10)
    assert draft.category == "documentation"
    assert "Card declined" in draft.headline and draft.body and draft.expected_effect
    assert draft.faq_answer is None


def test_llm_wording_is_merged_over_the_template(monkeypatch: pytest.MonkeyPatch) -> None:
    long_headline = " ".join(["word"] * 20)
    monkeypatch.setattr(
        llm, "complete_json",
        lambda *a, **k: {"headline": long_headline, "body": "", "faq_answer": "Update your card in Billing.", "extra": 1},
    )  # fmt: skip
    draft = write_recommendation(facts(query_count=12), 10)  # faq
    assert len(draft.headline.split()) == 12  # capped
    assert draft.body.startswith("12 customers asked")  # empty LLM field → template kept
    assert draft.faq_answer == "Update your card in Billing."
