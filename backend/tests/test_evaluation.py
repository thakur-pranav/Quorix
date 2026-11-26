"""Evaluation: the judge parser, the judge call, and a run's averages (fake LLM, no network)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import evaluation, llm
from app.config import settings
from app.evaluation import judge, parse_score, run_evaluation
from app.models import EvaluationRun, Message
from app.rag import engine
from tests.test_rag import PASSWORD, REFUND, index


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0.85", 0.85),
        ("Score: 0.7", 0.7),
        ("0.85/1", 0.85),
        ("0.85 / 1.00", 0.85),  # the reference read this as 0.851.00 → error → 0.0
        ("8/10", 0.8),
        ("4 out of 5", 0.8),
        (".5", 0.5),
        (0.9, 0.9),  # JSON numbers arrive as floats
        (1, 1.0),
        ("0", 0.0),  # a real zero is a score, not a failure
        ("8", None),  # another scale: untrusted, not clamped to 1.0
        ("1/0", None),
        ("garbage", None),
        ("", None),
        (None, None),
        (True, None),  # bool is an int subclass in Python
    ],
)
def test_parse_score(raw: object, expected: float | None) -> None:
    assert parse_score(raw) == expected


def fake_llm(monkeypatch: pytest.MonkeyPatch, judge_replies: dict[str, str]) -> list[dict[str, object]]:
    """Generator calls get an answer; judge calls get the reply for the metric named in the prompt."""
    calls: list[dict[str, object]] = []

    def complete(user: str, system: str, **kwargs: object) -> str:
        calls.append({"system": system, **kwargs})
        if system == engine.SYSTEM_PROMPT:
            return "Refunds take five business days [1]."
        for metric, marker in (("faithfulness", "factual claims"), ("answer_relevance", "address what was asked"), ("context_relevance", "share of these passages")):
            if marker in user:
                return judge_replies[metric]
        raise AssertionError("unexpected prompt")

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def test_judge_reads_json_and_keeps_the_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "judge_model", "judge-family-model")
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(llm, "complete", lambda *a, **k: seen.append(k) or json.dumps({"reason": "All claims are in [1].", "score": 0.9}))
    assert judge("prompt") == evaluation.Judgement(0.9, "All claims are in [1].")
    assert seen[0]["model"] == "judge-family-model" and seen[0]["temperature"] == 0.0 and seen[0]["json_mode"]


def test_judge_falls_back_to_the_regex_on_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "complete", lambda *a, **k: "Score: 0.7 because most claims are supported")
    assert judge("prompt").score == 0.7


def test_judge_failure_is_none_not_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def down(*_a: object, **_k: object) -> str:
        raise llm.LLMError("LLM unavailable after 4 attempts (HTTP 503)")

    monkeypatch.setattr(llm, "complete", down)
    verdict = judge("prompt")
    assert verdict.score is None and "503" in verdict.reason


def test_run_leaves_failed_judgements_out_of_the_averages(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    index(db, "org_a", REFUND, PASSWORD)
    fake_llm(
        monkeypatch,
        {
            "faithfulness": '{"reason": "Supported by [1].", "score": 1.0}',
            "answer_relevance": "I cannot rate this.",  # unreadable → None, not 0
            "context_relevance": '{"reason": "Only one of two passages helps.", "score": 0.4}',
        },
    )
    run, results = run_evaluation(db, "org_a", ["How long do refunds take?", "Refund timing?"])

    assert run.question_count == 2
    assert run.faithfulness == 1.0
    assert run.answer_relevance is None  # every judgement failed: no average, not 0.0
    assert run.context_relevance == 0.4
    assert run.failed_judgements == 2
    assert [f["metric"] for f in run.failures] == ["context_relevance", "context_relevance"]  # 0.4 < 0.5
    assert run.failures[0]["reason"] == "Only one of two passages helps."
    assert all(r.answer and 0.0 <= r.confidence <= 1.0 for r in results)  # retrieval confidence recorded
    assert db.scalars(select(Message)).all() == []  # evaluation never writes chat history
    assert db.scalars(select(EvaluationRun)).one().organization_id == "org_a"


def test_questions_with_nothing_retrieved_are_skipped_not_scored(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    index(db, "org_b", REFUND)  # only another org has docs
    fake_llm(monkeypatch, {})
    run, [result] = run_evaluation(db, "org_a", ["How long do refunds take?"])
    assert result.skipped_because == "nothing retrieved"
    assert run.question_count == 0 and run.faithfulness is None and run.failed_judgements == 0


def test_top_k_override_limits_the_passages(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    index(db, "org_a", REFUND, PASSWORD)
    fake_llm(monkeypatch, dict.fromkeys(evaluation.METRICS, '{"reason": "ok", "score": 1}'))
    result = evaluation.evaluate_question(db, "How long do refunds take?", "org_a", top_k=1)
    assert result.scores == dict.fromkeys(evaluation.METRICS, 1.0)
    assert len(engine.retrieve_only(db, "refunds", "org_a", top_k=1)) == 1
