"""Analytics API (SPEC section 4): overview, topics, reports, and running the batch.

Every query filters by the caller's org. Another org's topic or report is a 404.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import batch
from app.config import settings
from app.db import DbSession, SessionLocal
from app.models import Chunk, ClusterMember, Message, Report, Source, TopicCluster
from app.schemas import (
    AnalyticsRunOut,
    AnalyticsRunRequest,
    MemberQuery,
    OverviewOut,
    PeriodVolume,
    ReportOut,
    ReportSummaryOut,
    TopicDetailOut,
    TopicHistoryPoint,
    TopicOut,
    WeakChunk,
)
from app.tenant import CurrentTenant

logger = logging.getLogger(__name__)
router = APIRouter(tags=["insights"])

MEMBER_QUERIES_SHOWN = 30
WEAKEST_CHUNKS_SHOWN = 5
EXCERPT_CHARS = 320


def _latest_topic_period(db: Session, org: str) -> str | None:
    return db.scalar(select(func.max(TopicCluster.period)).where(TopicCluster.organization_id == org))


@router.get("/overview", response_model=OverviewOut)
def overview(tenant: CurrentTenant, db: DbSession) -> OverviewOut:
    customer = (Message.organization_id == tenant.org, Message.role == "customer")
    volume = db.execute(
        select(Message.period, func.count(), func.avg(Message.confidence))
        .where(*customer)
        .group_by(Message.period)
        .order_by(Message.period)
    ).all()
    volume_by_period = [PeriodVolume(period=p, query_count=n, mean_confidence=round(c or 0.0, 4)) for p, n, c in volume]
    if not volume_by_period:
        return OverviewOut(
            period=None, conversation_count=0, query_count=0, topic_count=0, unanswered_rate=0.0,
            mean_confidence=0.0, emerging_count=0, volume_by_period=[],
        )  # fmt: skip

    period = volume_by_period[-1].period
    in_period = (*customer, Message.period == period)
    conversations = db.scalar(select(func.count(func.distinct(Message.conversation_id))).where(*in_period)) or 0
    unanswered = db.scalar(
        select(func.count()).where(*in_period, Message.confidence < settings.low_confidence_threshold)
    ) or 0
    topics = db.execute(
        select(TopicCluster.trend, func.count())
        .where(TopicCluster.organization_id == tenant.org, TopicCluster.period == period)
        .group_by(TopicCluster.trend)
    ).all()
    latest = volume_by_period[-1]
    return OverviewOut(
        period=period,
        conversation_count=conversations,
        query_count=latest.query_count,
        topic_count=sum(n for _, n in topics),
        unanswered_rate=round(unanswered / latest.query_count, 4),
        mean_confidence=latest.mean_confidence,
        emerging_count=sum(n for trend, n in topics if trend == "emerging"),
        volume_by_period=volume_by_period,
    )


@router.get("/insights", response_model=list[TopicOut])
def list_topics(tenant: CurrentTenant, db: DbSession) -> list[TopicCluster]:
    """Topics of the latest analysed period, highest priority first."""
    period = _latest_topic_period(db, tenant.org)
    if period is None:
        return []
    stmt = (
        select(TopicCluster)
        .where(TopicCluster.organization_id == tenant.org, TopicCluster.period == period)
        .order_by(TopicCluster.rank)
    )
    return list(db.scalars(stmt))


def _history(db: Session, topic: TopicCluster) -> list[TopicHistoryPoint]:
    """Follow previous_cluster_id back through earlier periods (oldest first)."""
    points, current, seen = [], topic, set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        points.append(TopicHistoryPoint(period=current.period, query_count=current.query_count,
                                        mean_confidence=current.mean_confidence, trend=current.trend))  # fmt: skip
        if not current.previous_cluster_id:
            break
        current = db.scalar(
            select(TopicCluster).where(
                TopicCluster.id == current.previous_cluster_id, TopicCluster.organization_id == topic.organization_id
            )
        )
    return list(reversed(points))


def _weakest_chunks(db: Session, org: str, messages: list[Message]) -> list[WeakChunk]:
    """The passages this topic's questions landed on, worst-matching first: the pages to fix."""
    scores: dict[str, list[float]] = defaultdict(list)
    for message in messages:
        for chunk_id, score in zip(message.retrieved_chunk_ids or [], message.retrieved_scores or [], strict=False):
            scores[chunk_id].append(score)
    if not scores:
        return []
    # The most-retrieved passages are the ones customers actually land on; then sort by match.
    frequent = sorted(scores, key=lambda cid: -len(scores[cid]))[: WEAKEST_CHUNKS_SHOWN * 3]
    rows = db.execute(
        select(Chunk, Source.label)
        .join(Source, Source.id == Chunk.source_id)
        .where(Chunk.organization_id == org, Chunk.id.in_(frequent))
    ).all()
    chunks = [
        WeakChunk(
            chunk_id=chunk.id, source_label=label, heading_path=chunk.heading_path, url=chunk.url,
            excerpt=chunk.text[:EXCERPT_CHARS], times_retrieved=len(scores[chunk.id]),
            mean_similarity=round(sum(scores[chunk.id]) / len(scores[chunk.id]), 4),
        )  # fmt: skip
        for chunk, label in rows
    ]
    return sorted(chunks, key=lambda c: (c.mean_similarity, -c.times_retrieved))[:WEAKEST_CHUNKS_SHOWN]


@router.get("/insights/{topic_id}", response_model=TopicDetailOut)
def topic_detail(topic_id: str, tenant: CurrentTenant, db: DbSession) -> TopicDetailOut:
    topic = db.scalar(select(TopicCluster).where(TopicCluster.id == topic_id, TopicCluster.organization_id == tenant.org))
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    messages = list(
        db.scalars(
            select(Message)
            .join(ClusterMember, ClusterMember.message_id == Message.id)
            .where(ClusterMember.cluster_id == topic.id, Message.organization_id == tenant.org)
            .order_by(Message.confidence, Message.created_at)
        )
    )
    return TopicDetailOut(
        **TopicOut.model_validate(topic).model_dump(),
        history=_history(db, topic),
        member_queries=[
            MemberQuery(message_id=m.id, text=m.text, confidence=m.confidence, created_at=m.created_at)
            for m in messages[:MEMBER_QUERIES_SHOWN]
        ],
        weakest_chunks=_weakest_chunks(db, tenant.org, messages),
    )


@router.get("/reports/latest", response_model=ReportOut)
def latest_report(tenant: CurrentTenant, db: DbSession) -> Report:
    report = db.scalar(
        select(Report).where(Report.organization_id == tenant.org).order_by(Report.period.desc()).limit(1)
    )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report yet: run the analysis once you have questions.")
    return report


@router.get("/reports", response_model=list[ReportSummaryOut])
def list_reports(tenant: CurrentTenant, db: DbSession) -> list[Report]:
    return list(db.scalars(select(Report).where(Report.organization_id == tenant.org).order_by(Report.period.desc())))


def _run_in_background(org: str, period: str | None) -> None:
    """Own session: the request's session is closed by the time this runs."""
    with SessionLocal() as db:
        try:
            if period:
                batch.run_batch(db, org, period)
            else:
                batch.run_all_periods(db, org)
        except Exception:
            logger.exception("analytics batch failed for %s", org)


@router.post("/analytics/run", response_model=AnalyticsRunOut, status_code=status.HTTP_202_ACCEPTED)
def run_analytics(body: AnalyticsRunRequest, tenant: CurrentTenant, db: DbSession, tasks: BackgroundTasks) -> AnalyticsRunOut:
    """Queue the batch (one period, or all periods oldest first). 202: it runs after the response."""
    available = batch.periods_with_questions(db, tenant.org)
    if body.period is not None and body.period not in available:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No questions in {body.period}")
    periods = [body.period] if body.period else available
    tasks.add_task(_run_in_background, tenant.org, body.period)
    return AnalyticsRunOut(periods=periods)
