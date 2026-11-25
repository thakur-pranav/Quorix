"""Recommendations (SPEC section 7.12): turn a top topic into one concrete action.

Rules pick the CATEGORY (deterministic, explainable: "why FAQ?" has a one-line answer). The LLM
only writes the WORDING, and its JSON is merged over templated defaults, so a failed or partial
LLM reply still yields a complete recommendation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app import llm
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicFacts:
    name: str
    keywords: list[str]
    query_count: int
    growth: float
    trend: str
    mean_confidence: float
    severity: float
    supporting_queries: list[str]


@dataclass(frozen=True)
class Draft:
    category: str
    headline: str
    body: str
    expected_effect: str
    faq_answer: str | None
    rule: str  # which rule chose the category, for the "why?" question


def choose_category(topic: TopicFacts, median_count: float) -> tuple[str, str]:
    """SPEC 7.12 rules, in order. Returns (category, the rule that fired)."""
    low_confidence = topic.mean_confidence < settings.low_confidence_threshold
    if low_confidence and topic.severity >= settings.category_product_severity and topic.trend == "emerging":
        return "product", "rule 1: low confidence + high severity + emerging"
    if low_confidence:
        return "documentation", "rule 2: the docs don't answer it (low confidence)"
    if topic.query_count >= median_count and topic.severity < settings.category_faq_max_severity:
        return "faq", "rule 3: frequent and low severity"
    small = max(settings.category_issue_min_count, settings.category_issue_median_share * median_count)
    if topic.severity >= settings.category_issue_severity and topic.query_count <= small:
        return "customer_issue", "rule 4: severe but affecting few customers"
    if topic.severity >= settings.category_fallback_product_severity:
        return "product", "rule 5: fallback, fairly severe"
    return "faq", "rule 5: fallback, mild"


def _defaults(topic: TopicFacts, category: str) -> dict[str, str]:
    n, name = topic.query_count, topic.name
    return {
        "product": {
            "headline": f"Fix the product flow behind “{name}”",
            "body": f"{n} questions this period point to a product problem rather than missing docs. "
            "Customers hit it often enough, and badly enough, that a fix will cut support load.",
            "expected_effect": "Fewer tickets on this topic once the flow is fixed.",
        },
        "documentation": {
            "headline": f"Write or fix the docs for “{name}”",
            "body": f"{n} questions this period got weak matches in your docs, so customers didn't find an answer. "
            "Add a page or section that answers these questions directly.",
            "expected_effect": "Higher answer confidence and fewer unanswered questions on this topic.",
        },
        "faq": {
            "headline": f"Add an FAQ entry for “{name}”",
            "body": f"{n} customers asked about this. The docs cover it, but it's common enough to deserve "
            "a short, prominent FAQ answer.",
            "expected_effect": "Customers self-serve this question faster.",
        },
        "customer_issue": {
            "headline": f"Follow up with customers about “{name}”",
            "body": f"A small number of customers ({n}) hit a severe problem here. "
            "Reach out directly before it spreads or turns into churn.",
            "expected_effect": "Affected customers unblocked; early warning if it grows.",
        },
    }[category]


SYSTEM_PROMPT = """You write concise, specific recommendations for a support team, based on \
the customer questions they received. Reply with JSON only:
{"headline": "<under 12 words>", "body": "<2 to 4 sentences>", "expected_effect": "<one sentence>", \
"faq_answer": "<a short FAQ answer, or null>"}
Only use facts from the questions given. Don't invent product features or numbers."""


def write_recommendation(topic: TopicFacts, median_count: float) -> Draft:
    category, rule = choose_category(topic, median_count)
    wording = _defaults(topic, category)
    faq_answer: str | None = None
    questions = "\n".join(f"- {q}" for q in topic.supporting_queries)
    user = (
        f"Category (already decided): {category}\nTopic: {topic.name}\nKeywords: {', '.join(topic.keywords)}\n"
        f"Questions this period: {topic.query_count} (trend: {topic.trend}, growth {topic.growth:+.0%})\n"
        f"Customer questions with the weakest answers:\n{questions}"
    )
    try:
        data = llm.complete_json(user, SYSTEM_PROMPT, temperature=0.3, max_tokens=700)
        for key in ("headline", "body", "expected_effect"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                wording[key] = value.strip()
        if category == "faq" and isinstance(data.get("faq_answer"), str) and data["faq_answer"].strip():
            faq_answer = data["faq_answer"].strip()
    except llm.LLMError as exc:
        logger.info("recommendation wording unavailable, using template: %s", exc)

    headline = " ".join(wording["headline"].split()[:12])
    return Draft(category, headline, wording["body"][:1200], wording["expected_effect"][:400], faq_answer, rule)
