"""The monthly analytics batch (SPEC section 7): one period's questions → topics → trends →
priorities → report → recommendations.

Idempotent: running a period again deletes that period's topics and report first, so a re-run
replaces results instead of duplicating them. Periods run oldest first, because each period's
trends compare against the one before.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import embeddings, llm
from app.analytics import clustering, recommend, severity, trends
from app.config import settings
from app.models import ClusterMember, Message, Recommendation, Report, TopicCluster

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchResult:
    period: str
    question_count: int
    topic_count: int
    noise_count: int
    report_id: str | None  # None when there were too few questions to cluster


def periods_with_questions(db: Session, org: str) -> list[str]:
    stmt = (
        select(Message.period)
        .where(Message.organization_id == org, Message.role == "customer")
        .distinct()
        .order_by(Message.period)
    )
    return list(db.scalars(stmt))


def _previous_topics(db: Session, org: str, period: str) -> tuple[bool, list[trends.PreviousTopic]]:
    """Topics of the latest earlier period that has any. (False, []) if this is the first."""
    previous_period = db.scalar(
        select(func.max(TopicCluster.period)).where(TopicCluster.organization_id == org, TopicCluster.period < period)
    )
    if previous_period is None:
        return False, []
    rows = db.scalars(
        select(TopicCluster).where(TopicCluster.organization_id == org, TopicCluster.period == previous_period)
    )
    return True, [trends.PreviousTopic(t.id, t.centroid, t.query_count) for t in rows]


SUMMARY_PROMPT = """You write a 3 to 4 sentence summary of a month of customer support questions \
for a support lead. Use only the numbers and topics given. Plain prose, no lists, no preamble."""


def _summary(period: str, questions: int, unanswered: float, ranked: list[TopicCluster]) -> str:
    top = ranked[0] if ranked else None
    fallback = (
        f"In {period}, customers asked {questions} questions across {len(ranked)} topics. "
        f"{unanswered:.0%} got a weak match in the docs."
        + (f" The top priority is “{top.name}” ({top.query_count} questions, {top.trend})." if top else "")
    )
    lines = "\n".join(
        f"- {t.name}: {t.query_count} questions, trend {t.trend}, growth {t.growth:+.0%}, "
        f"mean confidence {t.mean_confidence:.2f}, severity {t.severity:.2f}"
        for t in ranked[:5]
    )
    user = f"Period: {period}\nQuestions: {questions}\nShare with weak doc matches: {unanswered:.0%}\nTop topics:\n{lines}"
    try:
        text = llm.complete(user, SUMMARY_PROMPT, temperature=0.3, max_tokens=settings.summary_max_tokens).strip()
    except llm.LLMError:
        return fallback
    return text[:1500] if text else fallback


def run_batch(db: Session, org: str, period: str) -> BatchResult:
    """Analyse one period for one organization. Commits; safe to re-run."""
    # Idempotency: wipe this period's previous results (members and recommendations cascade).
    db.execute(delete(TopicCluster).where(TopicCluster.organization_id == org, TopicCluster.period == period))
    db.execute(delete(Report).where(Report.organization_id == org, Report.period == period))
    db.flush()

    messages = list(
        db.scalars(
            select(Message)
            .where(Message.organization_id == org, Message.period == period, Message.role == "customer")
            .order_by(Message.created_at, Message.id)
        )
    )
    texts = [m.text for m in messages]
    confidences = [m.confidence or 0.0 for m in messages]

    topics, noise = clustering.discover_topics(texts, np.asarray(embeddings.embed(texts))) if texts else ([], 0)
    if not topics:
        db.commit()
        return BatchResult(period, len(messages), 0, noise, None)

    has_previous_period, previous = _previous_topics(db, org, period)
    max_count = max(len(t.indices) for t in topics)

    rows: list[TopicCluster] = []
    for topic in topics:
        members = [messages[i] for i in topic.indices]
        count = len(members)
        mean_confidence = round(float(np.mean([confidences[i] for i in topic.indices])), 4)
        rated = severity.score_severity(topic.name, [m.text for m in members])
        match = trends.match_previous(topic.centroid, previous)
        previous_count = match.query_count if match else 0
        growth = trends.compute_growth(count, previous_count)
        cluster = TopicCluster(
            organization_id=org,
            period=period,
            name=topic.name,
            keywords=topic.keywords,
            query_count=count,
            previous_query_count=previous_count,
            growth=growth,
            mean_confidence=mean_confidence,
            severity=rated.score,
            severity_reason=f"{rated.reason} [{rated.source}]",
            priority=trends.priority(count, max_count, growth, mean_confidence, rated.score),
            trend=trends.classify_trend(count, previous_count, growth, has_previous_period=has_previous_period),
            centroid=topic.centroid,
            previous_cluster_id=match.id if match else None,
        )
        cluster.members = [ClusterMember(organization_id=org, message_id=m.id) for m in members]
        rows.append(cluster)

    rows.sort(key=lambda c: (-c.priority, -c.query_count, c.name))
    for rank, cluster in enumerate(rows, start=1):
        cluster.rank = rank
    db.add_all(rows)
    db.flush()  # assigns ids, needed by the recommendations

    unanswered = sum(c < settings.low_confidence_threshold for c in confidences) / len(confidences)
    report = Report(
        organization_id=org,
        period=period,
        conversation_count=len({m.conversation_id for m in messages}),
        query_count=len(messages),
        unanswered_rate=round(unanswered, 4),
        summary=_summary(period, len(messages), unanswered, rows),
    )

    median_count = statistics.median(c.query_count for c in rows)
    confidence_of = {m.id: confidences[i] for i, m in enumerate(messages)}
    text_of = {m.id: m.text for m in messages}
    for cluster in rows[: settings.recommendation_count]:
        weakest = sorted(cluster.members, key=lambda cm: confidence_of[cm.message_id])
        supporting = [text_of[cm.message_id] for cm in weakest[: settings.recommendation_supporting_queries]]
        draft = recommend.write_recommendation(
            recommend.TopicFacts(
                name=cluster.name, keywords=list(cluster.keywords), query_count=cluster.query_count,
                growth=cluster.growth, trend=cluster.trend, mean_confidence=cluster.mean_confidence,
                severity=cluster.severity, supporting_queries=supporting,
            ),  # fmt: skip
            median_count,
        )
        report.recommendations.append(
            Recommendation(
                organization_id=org, cluster_id=cluster.id, cluster_name=cluster.name,
                category=draft.category, headline=draft.headline, body=draft.body,
                faq_answer=draft.faq_answer, supporting_queries=supporting, volume=cluster.query_count,
                growth=cluster.growth, expected_effect=draft.expected_effect,
            )  # fmt: skip
        )
    db.add(report)
    db.commit()
    logger.info("batch %s/%s: %d questions, %d topics, %d noise", org, period, len(messages), len(rows), noise)
    return BatchResult(period, len(messages), len(rows), noise, report.id)


def run_all_periods(db: Session, org: str) -> list[BatchResult]:
    """Every period with questions, oldest first, so trends always compare to fresh results."""
    return [run_batch(db, org, period) for period in periods_with_questions(db, org)]
