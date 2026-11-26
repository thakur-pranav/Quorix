"""Severity (SPEC section 7.6): how badly a topic blocks customers. 0 = curiosity, 1 = can't work.

Two scorers. A keyword rule that always works and is easy to inspect, and an LLM score with a
one-line reason. Final = the LLM score when it returns something valid, else the rule. The
reason is stored either way, so "why is this ranked high?" always has an answer.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app import llm
from app.config import settings

logger = logging.getLogger(__name__)

# Words that signal a customer is blocked or losing money.
HARD_TERMS = (
    "declined", "failed", "failing", "fails", "error", "errors", "broken", "stuck", "lost",
    "locked", "suspended", "blocked", "charged twice", "double charged", "overcharged",
    "refund", "cannot", "can't", "not working", "doesn't work", "missing", "wrong", "urgent",
)  # fmt: skip
# Phrasing that signals curiosity rather than a blocker.
SOFT_PHRASES = (
    "how do i", "how can i", "where is", "where can i", "what does", "what is", "can i",
    "is it possible", "difference between",
)  # fmt: skip


def _pattern(term: str) -> re.Pattern[str]:
    """Whole words or phrases only: "lost" must not match "almost", "error" not "terror"."""
    return re.compile(rf"(?<![\w']){re.escape(term)}(?![\w'])", re.IGNORECASE)


_HARD = [(term, _pattern(term)) for term in HARD_TERMS]
_SOFT = [(term, _pattern(term)) for term in SOFT_PHRASES]

# Anchored rubric (Day 5): with a bare 0..1 scale the LLM rated 13 of 15 topics 0.8-1.0, so
# severity stopped separating anything and every recommendation became "product". Described
# levels with examples, and judging the TYPICAL question, spread the scores out.
SYSTEM_PROMPT = """You rate how severe a customer support topic is, from a sample of its questions.

Judge the TYPICAL question in the sample, not the most dramatic one. Use this scale:
1 = curiosity: "what is", "how does X work", comparing options. Nothing is wrong.
2 = how-to: they want to do something and need the steps. Not blocked, just asking.
3 = confused: something surprised them (an unexpected number, a setting they can't find), \
but they can keep working.
4 = blocked: a task fails or is impossible (a payment declined, an action errors, an \
upgrade won't apply), with a workaround or no money lost yet.
5 = critical: they can't use the product at all, or they are losing money right now \
(locked out, charged wrongly, service cut off).

Most topics are 2 or 3. Use 5 only when most questions describe being locked out or \
losing money. Reply with JSON only: {"level": <1-5>, "reason": "<one sentence>"}"""


@dataclass(frozen=True)
class Severity:
    score: float
    reason: str
    source: str  # "llm" or "rule"


def rule_severity(text: str) -> Severity:
    """Base 0.35, +0.10 per distinct blocking term, -0.05 per distinct curiosity phrase, clamped."""
    hard = [term for term, pattern in _HARD if pattern.search(text)]
    soft = [term for term, pattern in _SOFT if pattern.search(text)]
    raw = settings.severity_base + settings.severity_hard_step * len(hard) - settings.severity_soft_step * len(soft)
    score = round(max(settings.severity_min, min(1.0, raw)), 3)
    parts = []
    if hard:
        parts.append(f"blocking words ({', '.join(hard[:5])})")
    if soft:
        parts.append(f"question phrasing ({', '.join(soft[:3])})")
    return Severity(score, "Keyword rule: " + ("; ".join(parts) or "no strong signals"), "rule")


def llm_severity(name: str, samples: list[str]) -> Severity | None:
    """The LLM's score and reason, or None if the call fails or the output is unusable."""
    questions = "\n".join(f"- {q}" for q in samples[: settings.severity_samples])
    try:
        data = llm.complete_json(f"Topic: {name}\nCustomer questions:\n{questions}", SYSTEM_PROMPT, temperature=0.0, max_tokens=settings.severity_max_tokens)
        level = data["level"]
        reason = str(data.get("reason", "")).strip()
    except (llm.LLMError, KeyError, TypeError) as exc:
        logger.info("LLM severity unavailable for %r: %s", name, exc)
        return None
    # LLM output is untrusted: only a whole level 1-5 counts (bool is an int in Python: reject it).
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 5 or not reason:
        return None
    return Severity(settings.severity_level_scores[level - 1], reason[:240], "llm")


def score_severity(name: str, samples: list[str]) -> Severity:
    rule = rule_severity(" ".join([name, *samples[: settings.severity_samples]]))
    return llm_severity(name, samples) or rule
