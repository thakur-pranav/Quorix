"""The batch end to end on planted stories (fake embeddings, no LLM): topics over time."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import count

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.batch import growth_text, run_analysis
from app.config import settings
from app.models import ClusterMember, Conversation, Message, Recommendation, Report, TopicCluster

TOPICS = {
    "refund": "refund money back card returned",
    "password": "password reset login locked email",
    "invoice": "invoice receipt download billing pdf",
}
FILLERS = ("today", "again", "urgently", "quickly", "still", "anyway", "seriously", "finally")
_serial = count()

# These test questions differ by one filler word, so many vectors are near-identical and UMAP's
# spectral initialisation can't separate them; it falls back to (seeded) random init. Real
# questions vary far more. Only this test data triggers it.
pytestmark = pytest.mark.filterwarnings("ignore:Spectral initialisation failed:UserWarning")


@pytest.fixture(autouse=True)
def cluster_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hdbscan_min_cluster_size", 6)


def ask(db: Session, org: str, period: str, topic: str, n: int, confidence: float) -> None:
    year, month = map(int, period.split("-"))
    conversation = Conversation(organization_id=org, session_id=f"s{next(_serial)}", synthetic=True)
    for i in range(n):
        conversation.messages.append(
            Message(
                organization_id=org, role="customer", text=f"{TOPICS[topic]} {FILLERS[i % len(FILLERS)]}",
                confidence=confidence, retrieved_chunk_ids=[], retrieved_scores=[], period=period,
                created_at=datetime(year, month, 1 + i % 27, 12, tzinfo=timezone.utc),
            )  # fmt: skip
        )
    db.add(conversation)
    db.commit()


@pytest.fixture
def story(db: Session) -> Session:
    ask(db, "org_a", "2026-09", "refund", 8, 0.30)
    ask(db, "org_a", "2026-09", "password", 8, 0.75)
    ask(db, "org_a", "2026-09", "invoice", 14, 0.80)
    ask(db, "org_a", "2026-10", "refund", 20, 0.30)
    ask(db, "org_a", "2026-10", "password", 8, 0.75)
    ask(db, "org_a", "2026-10", "invoice", 6, 0.80)
    ask(db, "org_b", "2026-10", "refund", 12, 0.30)  # another tenant: must never mix in
    return db


def topics_by_word(db: Session, period: str, org: str = "org_a") -> dict[str, TopicCluster]:
    rows = db.scalars(select(TopicCluster).where(TopicCluster.organization_id == org, TopicCluster.period == period))
    return {next(w for w in TOPICS if w in t.keywords): t for t in rows}


def test_two_month_story(story: Session) -> None:
    db = story
    results = run_analysis(db, "org_a")
    assert [(r.period, r.topic_count) for r in results] == [("2026-09", 3), ("2026-10", 3)]

    september = topics_by_word(db, "2026-09")
    assert {t.trend for t in september.values()} == {"baseline"}  # first month: nothing to compare

    october = topics_by_word(db, "2026-10")
    assert october["refund"].trend == "emerging"  # 8 → 20
    assert october["password"].trend == "recurring"  # 8 → 8
    assert october["invoice"].trend == "declining"  # 14 → 6
    assert october["refund"].previous_cluster_id == september["refund"].id
    # Clustered once: the same topic in both months, not two clusters glued together by similarity.
    assert october["refund"].name == september["refund"].name
    assert october["refund"].centroid == september["refund"].centroid
    assert (october["refund"].query_count, october["refund"].previous_query_count) == (20, 8)
    assert october["refund"].growth == pytest.approx(1.5)
    assert october["refund"].rank == 1  # biggest, fastest-growing, worst-answered

    report = db.scalars(select(Report).where(Report.organization_id == "org_a", Report.period == "2026-10")).one()
    assert report.query_count == 34 and report.conversation_count == 3
    assert report.unanswered_rate == pytest.approx(20 / 34, abs=1e-4)  # refund questions are below the threshold
    assert report.summary  # templated fallback without an LLM

    recommendations = report.recommendations
    assert 1 <= len(recommendations) <= settings.recommendation_count
    refund_rec = next(r for r in recommendations if r.cluster_id == october["refund"].id)
    assert refund_rec.category == "documentation"  # low confidence → the docs don't answer it
    assert len(refund_rec.supporting_queries) == settings.recommendation_supporting_queries


def test_running_a_period_twice_gives_the_same_result(story: Session) -> None:
    db = story
    run_analysis(db, "org_a")

    def snapshot() -> list[tuple[str, int, int, str, float]]:
        rows = db.scalars(select(TopicCluster).where(TopicCluster.period == "2026-10", TopicCluster.organization_id == "org_a"))
        return sorted((t.name, t.rank, t.query_count, t.trend, t.priority) for t in rows)

    first = snapshot()
    run_analysis(db, "org_a")
    assert snapshot() == first
    assert db.scalar(select(func.count()).select_from(Report).where(Report.period == "2026-10", Report.organization_id == "org_a")) == 1
    assert db.scalar(select(func.count()).select_from(ClusterMember).where(ClusterMember.organization_id == "org_a")) == 30 + 34
    assert db.scalar(select(func.count()).select_from(Recommendation).where(Recommendation.organization_id == "org_a")) == 6  # 3 topics per month → 3 recommendations each


def test_batch_is_tenant_scoped(story: Session) -> None:
    db = story
    run_analysis(db, "org_a")
    org_b = db.scalars(select(TopicCluster).where(TopicCluster.organization_id == "org_b")).all()
    assert org_b == []  # org_a's run never touched org_b
    member_messages = db.scalars(
        select(Message.organization_id).join(ClusterMember, ClusterMember.message_id == Message.id).distinct()
    ).all()
    assert member_messages == ["org_a"]


def test_too_few_questions_produces_no_report(db: Session) -> None:
    ask(db, "org_a", "2026-11", "refund", 5, 0.5)
    [result] = run_analysis(db, "org_a")
    assert result.report_id is None and result.topic_count == 0
    assert db.scalars(select(Report)).all() == []


def test_a_topic_that_skips_a_month_restarts_without_a_link(db: Session) -> None:
    """Refund: 8 → 3 → 10. October's 3 is under topic_min_period_questions, so no October row;
    November compares with the TRUE October count (3), and has no row to link to."""
    for period, refunds in (("2026-09", 8), ("2026-10", 3), ("2026-11", 10)):
        ask(db, "org_a", period, "refund", refunds, 0.30)
        ask(db, "org_a", period, "password", 8, 0.75)
        ask(db, "org_a", period, "invoice", 8, 0.80)
    run_analysis(db, "org_a")

    assert "refund" not in topics_by_word(db, "2026-10")
    refund = topics_by_word(db, "2026-11")["refund"]
    assert (refund.query_count, refund.previous_query_count, refund.previous_cluster_id) == (10, 3, None)
    assert refund.trend == "emerging"  # +233% from a small base
    password = topics_by_word(db, "2026-11")["password"]
    assert password.previous_cluster_id == topics_by_word(db, "2026-10")["password"].id  # chain intact


def test_only_the_window_is_analysed(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "analytics_window_months", 2)
    for period in ("2026-08", "2026-09", "2026-10"):
        ask(db, "org_a", period, "refund", 8, 0.30)
        ask(db, "org_a", period, "password", 8, 0.75)
    results = run_analysis(db, "org_a")

    assert [r.period for r in results] == ["2026-09", "2026-10"]  # August is outside the window
    assert topics_by_word(db, "2026-08") == {}
    assert {t.trend for t in topics_by_word(db, "2026-09").values()} == {"baseline"}  # oldest in window


def test_growth_text_caps_like_the_priority_formula() -> None:
    assert growth_text(0, 17.0, "emerging") == "new this month"
    assert growth_text(0, 17.0, "baseline") == "first analysed month, no comparison"  # not "new"
    assert growth_text(8, 1.5, "emerging") == "+150%"
    assert growth_text(1, 16.0, "emerging") == "more than +300%"  # 1 → 17 is true, but reads as a crisis
