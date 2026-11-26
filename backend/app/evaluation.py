"""Reference-free RAG evaluation (SPEC section 8): three RAGAS-style metrics with an LLM judge.

- Faithfulness: are the answer's claims supported by the retrieved passages? (the generator)
- Answer relevance: does the answer address the question? (the generator)
- Context relevance: are the retrieved passages useful for the question? (the retriever)

Reference-free: no hand-written gold answers, so it can be re-run after any change to the docs,
the chunker or top_k for the cost of the API calls. Implemented directly instead of importing
the `ragas` package: three metric definitions don't justify its LangChain dependency tree.

Judge output is untrusted. It's asked for JSON with a reason BEFORE the score (reasoning first
makes judges more accurate, and the reason makes hand-checking possible). If the reply isn't
JSON, the SPEC's regex reads the first number from the raw text. A failed or unreadable
judgement is None: left out of the averages and counted, never scored as 0 (the reference
turned "0.85 / 1.00" into 0.0 and averaged failures in as zeros).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import llm
from app.config import settings
from app.models import EvaluationRun
from app.rag import engine
from app.vector_store import Hit

logger = logging.getLogger(__name__)

METRICS = ("faithfulness", "answer_relevance", "context_relevance")

JUDGE_SYSTEM = """You are a strict evaluator of a customer support assistant. Think about the \
case, then reply with JSON only, the reason first: {"reason": "<one sentence>", "score": <number from 0 to 1>}"""

# Each metric gets a described scale: a bare "rate 0 to 1" inflates (Day 5, severity).
PROMPTS = {
    "faithfulness": (
        "Passages:\n{context}\n\nAnswer:\n{answer}\n\n"
        "Of the factual claims in the answer, what share is supported by the passages?\n"
        "1.0 = every claim is stated in the passages. An answer that says the passages don't cover "
        "the question is also 1.0.\n"
        "0.5 = about half the claims are supported; the rest come from outside knowledge or guessing.\n"
        "0.0 = the claims are not in the passages, or contradict them."
    ),
    "answer_relevance": (
        "Question:\n{question}\n\nAnswer:\n{answer}\n\n"
        "Does the answer address what was asked? Judge relevance only, not correctness.\n"
        "1.0 = it directly answers this question.\n"
        "0.5 = partly: it answers a related question, or buries the answer in unrelated text.\n"
        "0.0 = it doesn't address the question, or only says it can't answer."
    ),
    "context_relevance": (
        "Question:\n{question}\n\nRetrieved passages:\n{context}\n\n"
        "What share of these passages is useful for answering the question?\n"
        "1.0 = all of them. 0.5 = about half. 0.0 = none of them."
    ),
}

_NUMBER = re.compile(r"\d*\.?\d+")  # SPEC section 8
_FRACTION = re.compile(r"(\d*\.?\d+)\s*(?:/|out of)\s*(\d*\.?\d+)", re.IGNORECASE)


def parse_score(raw: object) -> float | None:
    """A judge's score in [0, 1], or None if there's no usable one.

    "0.85" → 0.85; "Score: 0.7" → 0.7; "0.85 / 1.00" → 0.85; "8/10" → 0.8. A bare number
    outside [0, 1] ("8") is None, not clamped to 1.0: it's on some other scale, so it's untrusted.
    """
    if raw is None or isinstance(raw, bool):  # bool is an int subclass: True must not read as 1
        return None
    text = str(raw)
    fraction = _FRACTION.search(text)
    if fraction:
        numerator, denominator = float(fraction.group(1)), float(fraction.group(2))
        value = numerator / denominator if denominator else -1.0
    else:
        number = _NUMBER.search(text)
        if number is None:
            return None
        value = float(number.group())
    return round(value, 4) if 0.0 <= value <= 1.0 else None


@dataclass(frozen=True)
class Judgement:
    score: float | None  # None = the judge failed or gave nothing usable
    reason: str


def judge(prompt: str) -> Judgement:
    """One judge call at temperature 0 on the judge model. Never raises."""
    try:
        raw = llm.complete(
            prompt, JUDGE_SYSTEM, temperature=0.0, max_tokens=settings.judge_max_tokens,
            json_mode=True, model=settings.judge_model,
        )  # fmt: skip
    except llm.LLMError as exc:
        logger.warning("judge call failed: %s", exc)
        return Judgement(None, f"judge call failed: {exc}")
    try:
        data = llm.parse_json_object(raw)
    except llm.LLMError:
        return Judgement(parse_score(raw), "")  # not JSON: the SPEC regex on the raw text
    return Judgement(parse_score(data.get("score")), str(data.get("reason", "")).strip()[:300])


def _context(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{n}] {hit.heading_path}\n{hit.text}" for n, hit in enumerate(hits, start=1))


@dataclass
class QuestionResult:
    question: str
    confidence: float
    answer: str | None  # None = nothing retrieved or generation failed: the question is skipped
    scores: dict[str, float | None] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    skipped_because: str | None = None
    retrieved: list[tuple[str | None, str]] = field(default_factory=list)  # (url, heading), rank order


def evaluate_question(db: Session, question: str, org: str, top_k: int | None = None) -> QuestionResult:
    """Retrieve (no logging), generate with the chat prompt, then judge the three metrics.

    Generates even below the low-confidence threshold: this measures the retriever and the
    generator, and lets us check whether low confidence goes with low faithfulness.
    """
    hits = engine.retrieve_only(db, question, org, top_k)
    confidence = engine.compute_confidence([hit.similarity for hit in hits])
    retrieved = [(hit.url, hit.heading_path) for hit in hits]
    if not hits:
        return QuestionResult(question, confidence, None, skipped_because="nothing retrieved")
    system, user = engine.build_prompt(question, hits)
    try:
        answer = llm.complete(user, system, temperature=settings.chat_temperature, max_tokens=settings.chat_max_tokens)
    except llm.LLMError as exc:
        return QuestionResult(question, confidence, None, skipped_because=f"generation failed: {exc}", retrieved=retrieved)

    context = _context(hits)
    result = QuestionResult(question, confidence, answer, retrieved=retrieved)
    for metric in METRICS:
        verdict = judge(PROMPTS[metric].format(question=question, answer=answer, context=context))
        result.scores[metric] = verdict.score
        result.reasons[metric] = verdict.reason
    return result


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def run_evaluation(
    db: Session, org: str, questions: list[str], *, top_k: int | None = None
) -> tuple[EvaluationRun, list[QuestionResult]]:
    """Evaluate every question, store the run, and return it with the per-question results."""
    if not settings.judge_model or settings.judge_model == settings.groq_model:
        logger.warning("the generator's own model is judging: expect self-preference bias (set JUDGE_MODEL)")

    results = []
    for n, question in enumerate(questions, start=1):
        results.append(evaluate_question(db, question, org, top_k))
        logger.info("evaluated %d/%d", n, len(questions))

    answered = [r for r in results if r.answer is not None]
    averages = {m: _mean([s for r in answered if (s := r.scores[m]) is not None]) for m in METRICS}
    failed = sum(r.scores[m] is None for r in answered for m in METRICS)
    failures = sorted(
        (
            {
                "question": r.question, "metric": m, "score": r.scores[m], "reason": r.reasons[m],
                "confidence": r.confidence, "answer": (r.answer or "")[:400],
            }  # fmt: skip
            for r in answered
            for m in METRICS
            if (score := r.scores[m]) is not None and score < settings.eval_failure_threshold
        ),
        key=lambda f: f["score"],  # type: ignore[arg-type, return-value]
    )

    run = EvaluationRun(
        organization_id=org,
        question_count=len(answered),
        failed_judgements=failed,
        faithfulness=averages["faithfulness"],
        answer_relevance=averages["answer_relevance"],
        context_relevance=averages["context_relevance"],
        failures=failures[: settings.eval_failures_kept],
    )
    db.add(run)
    db.commit()
    skipped = len(results) - len(answered)
    logger.info("evaluation %s: %d answered, %d skipped, %d failed judgements", org, len(answered), skipped, failed)
    return run, results
