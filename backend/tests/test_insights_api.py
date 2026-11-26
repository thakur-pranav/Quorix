"""Analytics API end to end: run the batch through the API, then read every endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Message, Source
from tests.test_batch import ask
from tests.tokens import auth_header

A, B = auth_header(org="org_a"), auth_header(org="org_b")
pytestmark = pytest.mark.filterwarnings("ignore:Spectral initialisation failed:UserWarning")


@pytest.fixture
def analysed(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "hdbscan_min_cluster_size", 6)
    source = Source(organization_id="org_a", kind="website", label="Help Center", location="https://x.test")
    source.chunks = [Chunk(id="chk_refundpage1", organization_id="org_a", heading_path="Billing › Refunds", text="Refunds take 5 days.")]
    db.add(source)
    db.commit()
    ask(db, "org_a", "2026-09", "refund", 8, 0.30)
    ask(db, "org_a", "2026-09", "password", 8, 0.75)
    ask(db, "org_a", "2026-09", "invoice", 14, 0.80)
    ask(db, "org_a", "2026-10", "refund", 20, 0.30)
    ask(db, "org_a", "2026-10", "password", 8, 0.75)
    ask(db, "org_a", "2026-10", "invoice", 6, 0.80)
    for message in db.scalars(select(Message).where(Message.text.contains("refund"))):
        message.retrieved_chunk_ids, message.retrieved_scores = ["chk_refundpage1"], [0.3]
    db.commit()

    res = client.post("/api/analytics/run", headers=A, json={})
    assert res.status_code == 202
    assert res.json() == {"status": "queued", "periods": ["2026-09", "2026-10"]}
    return client


def test_overview(analysed: TestClient) -> None:
    body = analysed.get("/api/overview", headers=A).json()
    assert body["period"] == "2026-10"
    assert (body["queryCount"], body["topicCount"], body["emergingCount"]) == (34, 3, 1)
    assert body["unansweredRate"] == pytest.approx(20 / 34, abs=1e-4)
    assert [p["queryCount"] for p in body["volumeByPeriod"]] == [30, 34]
    histogram = body["confidenceHistogram"]
    assert len(histogram) == settings.overview_histogram_bins and histogram[0]["start"] == 0.0
    assert sum(b["count"] for b in histogram) == 34  # every October question in exactly one bin
    assert {b["start"] for b in histogram if b["count"]} == {0.3, 0.75, 0.8}  # refund, password, invoice
    assert body["lowConfidenceThreshold"] == settings.low_confidence_threshold


def test_insights_list_and_detail(analysed: TestClient) -> None:
    topics = analysed.get("/api/insights", headers=A).json()
    assert [t["rank"] for t in topics] == [1, 2, 3]
    assert {t["period"] for t in topics} == {"2026-10"}
    refund = next(t for t in topics if "refund" in t["keywords"])
    assert refund["trend"] == "emerging"

    detail = analysed.get(f"/api/insights/{refund['id']}", headers=A).json()
    assert [h["period"] for h in detail["history"]] == ["2026-09", "2026-10"]
    assert [h["queryCount"] for h in detail["history"]] == [8, 20]
    assert len(detail["memberQueries"]) == 20
    [chunk] = detail["weakestChunks"]  # the passage refund questions keep landing on
    assert chunk["chunkId"] == "chk_refundpage1" and chunk["timesRetrieved"] == 20
    assert chunk["meanSimilarity"] == pytest.approx(0.3)


def test_reports(analysed: TestClient) -> None:
    latest = analysed.get("/api/reports/latest", headers=A).json()
    assert latest["period"] == "2026-10" and latest["summary"]
    assert 1 <= len(latest["recommendations"]) <= 6
    assert {"headline", "category", "supportingQueries", "expectedEffect"} <= set(latest["recommendations"][0])
    assert [r["period"] for r in analysed.get("/api/reports", headers=A).json()] == ["2026-10", "2026-09"]


def test_other_orgs_see_nothing(analysed: TestClient) -> None:
    topic_id = analysed.get("/api/insights", headers=A).json()[0]["id"]
    assert analysed.get(f"/api/insights/{topic_id}", headers=B).status_code == 404
    assert analysed.get("/api/insights", headers=B).json() == []
    assert analysed.get("/api/reports/latest", headers=B).status_code == 404
    empty = analysed.get("/api/overview", headers=B).json()
    assert empty["queryCount"] == 0 and empty["confidenceHistogram"] == []


def test_run_validation(client: TestClient) -> None:
    assert client.post("/api/analytics/run", json={}).status_code == 401
    # One run always covers the whole window: a per-month option would split topics again.
    assert client.post("/api/analytics/run", headers=A, json={"period": "2026-10"}).status_code == 422
    nothing = client.post("/api/analytics/run", headers=A, json={})
    assert nothing.status_code == 202 and nothing.json()["periods"] == []  # no questions: nothing queued
    assert client.get("/api/reports/latest", headers=A).json()["detail"].startswith("No report yet")
