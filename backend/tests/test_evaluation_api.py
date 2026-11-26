"""GET /api/evaluation/latest: the newest run of the caller's org, camelCase, 404 otherwise."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EvaluationRun
from tests.tokens import auth_header

A, B = auth_header(org="org_a"), auth_header(org="org_b")
FAILURE = {
    "question": "Can I pay with PayPal?", "metric": "context_relevance", "score": 0.2,
    "reason": "Only one passage mentions payment methods.", "confidence": 0.48, "answer": "Yes [1].",
}  # fmt: skip


def run(org: str, day: int, faithfulness: float | None) -> EvaluationRun:
    return EvaluationRun(
        organization_id=org, ran_at=datetime(2026, 11, day, tzinfo=timezone.utc), question_count=60,
        failed_judgements=1, faithfulness=faithfulness, answer_relevance=0.99, context_relevance=0.55,
        failures=[FAILURE],
    )  # fmt: skip


def test_no_run_yet_is_404(client: TestClient) -> None:
    res = client.get("/api/evaluation/latest", headers=A)
    assert res.status_code == 404 and "run_evaluation" in res.json()["detail"]


def test_latest_run_of_the_callers_org(client: TestClient, db: Session) -> None:
    db.add_all([run("org_a", 20, 0.90), run("org_a", 26, 0.95), run("org_b", 27, 0.10)])
    db.commit()

    body = client.get("/api/evaluation/latest", headers=A).json()
    assert body["ranAt"].startswith("2026-11-26") and body["faithfulness"] == 0.95  # newest, not org_b's
    assert body["failedJudgements"] == 1 and body["questionCount"] == 60
    assert body["failures"] == [FAILURE]
    assert client.get("/api/evaluation/latest", headers=B).json()["faithfulness"] == 0.10


def test_a_metric_with_no_usable_judgements_is_null(client: TestClient, db: Session) -> None:
    db.add(run("org_a", 26, None))
    db.commit()
    assert client.get("/api/evaluation/latest", headers=A).json()["faithfulness"] is None


def test_requires_a_token(client: TestClient) -> None:
    assert client.get("/api/evaluation/latest").status_code == 401
