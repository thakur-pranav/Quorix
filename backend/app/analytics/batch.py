"""The analytics batch (SPEC section 7, with the Day 5 "topics over time" change).

All questions of the window (the latest `analytics_window_months` months) are clustered ONCE.
Each topic is then counted per month, giving one TopicCluster row per topic per month, linked
to the same topic's row the month before. Trends compare a topic with ITSELF, so there is no
guesswork about whether October's cluster "is" September's: that's what per-month clustering
plus centroid matching got wrong (it split topics differently every month).

Idempotent: a run deletes the window's topics and reports and rebuilds them. Re-clustering the
window can rename or regroup past months slightly as new data arrives; the latest run wins.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import embeddings, llm
from app.analytics import clustering, recommend, severity, trends
from app.config import settings
from app.models import ClusterMember, Message, Recommendation, Report, TopicCluster, new_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchResult:
    period: str
    question_count: int
    topic_count: int
    noise_count: int  # questions in no topic at all
    report_id: str | None  # None when there were too few questions to cluster


def periods_with_questions(db: Session, org: str) -> list[str]:
    stmt = (
        select(Message.period)
        .where(Message.organization_id == org, Message.role == "customer")
        .distinct()
        .order_by(Message.period)
    )
    return list(db.scalars(stmt))


def window_periods(db: Session, org: str) -> list[str]:
    """The months one run analyses: the latest `analytics_window_months` with questions, oldest first."""
    return periods_with_questions(db, org)[-settings.analytics_window_months :]


SUMMARY_PROMPT = """You write a 3 to 4 sentence summary of a month of customer support questions \
for a support lead. Use only the numbers and topics given. Plain prose, no lists, no preamble."""


def growth_text(previous_count: int, growth: float, trend: str) -> str:
    """Growth for people: "new this month", or a percentage capped like the priority formula.

    1 → 17 questions is +1600%: true, but it reads as a crisis. Above the cap, say so instead.
    A baseline month has nothing to compare with, which is not the same as "new".
    """
    if trend == "baseline":
        return "first analysed month, no comparison"
    if previous_count == 0:
        return "new this month"
    if growth > settings.priority_growth_cap:
        return f"more than +{settings.priority_growth_cap:.0%}"
    return f"{growth:+.0%}"


def _summary(period: str, questions: int, unanswered: float, ranked: list[TopicCluster]) -> str:
    top = ranked[0] if ranked else None
    fallback = (
        f"In {period}, customers asked {questions} questions across {len(ranked)} topics. "
        f"{unanswered:.0%} got a weak match in the docs."
        + (f" The top priority is “{top.name}” ({top.query_count} questions, {top.trend})." if top else "")
    )
    lines = "\n".join(
        f"- {t.name}: {t.query_count} questions (previous month {t.previous_query_count}), trend {t.trend}, "
        f"growth {growth_text(t.previous_query_count, t.growth, t.trend)}, mean confidence {t.mean_confidence:.2f}, "
        f"severity {t.severity:.2f}"
        for t in ranked[:5]
    )
    user = f"Period: {period}\nQuestions: {questions}\nShare with weak doc matches: {unanswered:.0%}\nTop topics:\n{lines}"
    try:
        text = llm.complete(user, SUMMARY_PROMPT, temperature=0.3, max_tokens=settings.summary_max_tokens).strip()
    except llm.LLMError:
        return fallback
    return text[:1500] if text else fallback


def _topic_rows(org: str, topic: clustering.Topic, messages: list[Message], periods: list[str]) -> list[TopicCluster]:
    """One topic → its rows, one per month where it has enough questions, each linked to the last."""
    by_period: dict[str, list[Message]] = defaultdict(list)
    for i in topic.indices:
        by_period[messages[i].period].append(messages[i])
    # Once per topic, not per month: the topic is the same object in every month.
    rated = severity.score_severity(topic.name, [messages[i].text for i in topic.indices])

    rows: list[TopicCluster] = []
    previous_row: TopicCluster | None = None
    for p, period in enumerate(periods):
        members = by_period.get(period, [])
        count = len(members)
        previous_count = len(by_period.get(periods[p - 1], [])) if p > 0 else 0  # true count, row or not
        if count < settings.topic_min_period_questions:
            previous_row = None  # the topic skipped this month: next month's row has no link
            continue
        growth = trends.compute_growth(count, previous_count)
        row = TopicCluster(
            id=new_id("ins"),  # set now, so the next month's row can link to it before the flush
            organization_id=org,
            period=period,
            name=topic.name,
            keywords=topic.keywords,
            query_count=count,
            previous_query_count=previous_count,
            growth=growth,
            mean_confidence=round(float(np.mean([m.confidence or 0.0 for m in members])), 4),
            severity=rated.score,
            severity_reason=f"{rated.reason} [{rated.source}]",
            trend=trends.classify_trend(count, previous_count, growth, has_previous_period=p > 0),
            centroid=topic.centroid,
            previous_cluster_id=previous_row.id if previous_row else None,
        )
        row.members = [ClusterMember(organization_id=org, message_id=m.id) for m in members]
        rows.append(row)
        previous_row = row
    return rows


def _report(org: str, period: str, messages: list[Message], rows: list[TopicCluster]) -> Report:
    """Rank one month's topics, then write its report and recommendations for the top ones."""
    max_count = max((r.query_count for r in rows), default=0)
    for r in rows:
        r.priority = trends.priority(r.query_count, max_count, r.growth, r.mean_confidence, r.severity)
    rows.sort(key=lambda r: (-r.priority, -r.query_count, r.name))
    for rank, r in enumerate(rows, start=1):
        r.rank = rank

    confidence_of = {m.id: m.confidence or 0.0 for m in messages}
    unanswered = sum(c < settings.low_confidence_threshold for c in confidence_of.values()) / len(messages)
    report = Report(
        organization_id=org,
        period=period,
        conversation_count=len({m.conversation_id for m in messages}),
        query_count=len(messages),
        unanswered_rate=round(unanswered, 4),
        summary=_summary(period, len(messages), unanswered, rows),
    )
    if not rows:
        return report

    median_count = statistics.median(r.query_count for r in rows)
    text_of = {m.id: m.text for m in messages}
    for r in rows[: settings.recommendation_count]:
        weakest = sorted(r.members, key=lambda cm: confidence_of[cm.message_id])
        supporting = [text_of[cm.message_id] for cm in weakest[: settings.recommendation_supporting_queries]]
        draft = recommend.write_recommendation(
            recommend.TopicFacts(
                name=r.name, keywords=list(r.keywords), query_count=r.query_count, growth=r.growth,
                trend=r.trend, mean_confidence=r.mean_confidence, severity=r.severity,
                supporting_queries=supporting,
            ),  # fmt: skip
            median_count,
        )
        report.recommendations.append(
            Recommendation(
                organization_id=org, cluster_id=r.id, cluster_name=r.name,
                category=draft.category, headline=draft.headline, body=draft.body,
                faq_answer=draft.faq_answer, supporting_queries=supporting, volume=r.query_count,
                growth=r.growth, expected_effect=draft.expected_effect,
            )  # fmt: skip
        )
    return report


def run_analysis(db: Session, org: str) -> list[BatchResult]:
    """Analyse the org's window: cluster once, then trends, ranks and a report per month. Commits."""
    periods = window_periods(db, org)
    if not periods:
        return []
    # Idempotency: wipe the window's previous results (members and recommendations cascade).
    # Through the ORM, not a bulk DELETE: a bulk delete leaves already-loaded objects in the
    # session, and SQLite then reuses their integer ids for the new rows (identity-map clash).
    old = db.scalars(select(TopicCluster).where(TopicCluster.organization_id == org, TopicCluster.period.in_(periods)))
    old_reports = db.scalars(select(Report).where(Report.organization_id == org, Report.period.in_(periods)))
    for row in [*old, *old_reports]:
        db.delete(row)
    db.flush()

    messages = list(
        db.scalars(
            select(Message)
            .where(Message.organization_id == org, Message.role == "customer", Message.period.in_(periods))
            .order_by(Message.created_at, Message.id)
        )
    )
    texts = [m.text for m in messages]
    topics, _ = clustering.discover_topics(texts, np.asarray(embeddings.embed(texts)))
    in_period: dict[str, list[Message]] = defaultdict(list)
    for m in messages:
        in_period[m.period].append(m)
    if not topics:
        db.commit()
        return [BatchResult(p, len(in_period[p]), 0, len(in_period[p]), None) for p in periods]

    rows_by_period: dict[str, list[TopicCluster]] = defaultdict(list)
    for topic in topics:
        for row in _topic_rows(org, topic, messages, periods):
            rows_by_period[row.period].append(row)

    clustered = {i for topic in topics for i in topic.indices}
    noise_of = defaultdict(int)
    for i, m in enumerate(messages):
        noise_of[m.period] += i not in clustered

    results = []
    for period in periods:
        rows = rows_by_period[period]
        db.add_all(rows)
        report = _report(org, period, in_period[period], rows)
        db.add(report)
        db.flush()  # ids for the result; also surfaces any constraint error at its month
        results.append(BatchResult(period, len(in_period[period]), len(rows), noise_of[period], report.id))
        logger.info("analysis %s/%s: %d questions, %d topics", org, period, len(in_period[period]), len(rows))
    db.commit()
    return results
