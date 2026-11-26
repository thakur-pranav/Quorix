"""Tune HDBSCAN's min_cluster_size on seeded data (ROADMAP Day 5).

For each candidate size: run the full analysis (the whole window clustered once), then measure
- topics and noise % per period,
- against the true topic labels written by seed_conversations.py (noise counts as its own group):
  homogeneity (is each cluster about ONE topic? what makes a topic actionable),
  completeness (does each topic stay in ONE cluster? what keeps trends stable) and
  ARI (overall agreement, 1.0 = identical grouping, 0 = chance; it punishes splitting a topic
  into pure sub-topics as hard as mixing topics, so it understates quality here),
- whether the planted trends were caught: the growing topic should be "emerging" in the last
  two months, and the fading topic "declining" in the middle month.

A question in a topic that misses topic_min_period_questions in its month has no row there, so
it counts as noise for that month: the numbers measure what the Insights page shows.

`--match-thresholds` replays the OLD design's month-to-month centroid matching on stored
per-month clusters. It's the experiment that showed matching can't work (same-topic and
different-topic similarities overlap), which is why the batch now clusters the window once.

Run it with LLM_PROVIDER=none so names and severity use the free fallbacks; clustering doesn't
depend on them. Usage (from backend/):
    LLM_PROVIDER=none python -m scripts.tune_clusters --org org_demo --sizes 6 10 15
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score, homogeneity_completeness_v_measure
from sqlalchemy import select

from app.analytics import trends
from app.analytics.batch import run_analysis
from app.config import settings
from app.db import SessionLocal
from app.models import ClusterMember, Message, TopicCluster

LABELS_PATH = Path(__file__).resolve().parents[2] / "docs" / "experiments" / "seed_labels.json"
GROWING = "Troubleshooting a declined credit card charge"
FADING = "Payments for customers in India"


def evaluate(org: str, topic_of: dict[tuple[str, str], str]) -> list[dict[str, object]]:
    rows = []
    with SessionLocal() as db:
        periods = sorted({p for (p, _) in topic_of})
        for period in periods:
            messages = db.scalars(
                select(Message).where(Message.organization_id == org, Message.period == period, Message.role == "customer")
            ).all()
            cluster_of = dict(
                db.execute(
                    select(ClusterMember.message_id, ClusterMember.cluster_id)
                    .join(TopicCluster, TopicCluster.id == ClusterMember.cluster_id)
                    .where(TopicCluster.organization_id == org, TopicCluster.period == period)
                ).all()
            )
            labelled = [m for m in messages if (period, m.text) in topic_of]
            truth = [topic_of[(period, m.text)] for m in labelled]
            predicted = [cluster_of.get(m.id, "noise") for m in labelled]
            topics = db.scalars(
                select(TopicCluster).where(TopicCluster.organization_id == org, TopicCluster.period == period)
            ).all()

            def trend_of(label: str) -> str:
                """Trend of the cluster holding most of this label's questions ('noise' if none)."""
                ids = Counter(cluster_of.get(m.id, "noise") for m in labelled if topic_of[(period, m.text)] == label)
                best = ids.most_common(1)[0][0] if ids else "noise"
                return next((t.trend for t in topics if t.id == best), "noise")

            rows.append(
                {
                    "period": period,
                    "questions": len(messages),
                    "topics": len(topics),
                    "noise_pct": round(100 * sum(p == "noise" for p in predicted) / max(1, len(predicted)), 1),
                    "homogeneity": round(homogeneity_completeness_v_measure(truth, predicted)[0], 3),
                    "completeness": round(homogeneity_completeness_v_measure(truth, predicted)[1], 3),
                    "ari": round(adjusted_rand_score(truth, predicted), 3),
                    "growing": trend_of(GROWING),
                    "fading": trend_of(FADING),
                }
            )
    return rows


def dominant_labels(org: str, topic_of: dict[tuple[str, str], str]) -> dict[str, list[tuple[TopicCluster, str]]]:
    """Per period: each stored cluster with the true topic most of its questions belong to."""
    out: dict[str, list[tuple[TopicCluster, str]]] = {}
    with SessionLocal() as db:
        clusters = db.scalars(select(TopicCluster).where(TopicCluster.organization_id == org)).all()
        for cluster in clusters:
            texts = db.scalars(
                select(Message.text).join(ClusterMember, ClusterMember.message_id == Message.id)
                .where(ClusterMember.cluster_id == cluster.id)
            ).all()  # fmt: skip
            label = Counter(topic_of.get((cluster.period, t), "unlabelled") for t in texts).most_common(1)[0][0]
            db.expunge(cluster)
            out.setdefault(cluster.period, []).append((cluster, label))
    return out


def evaluate_matching(org: str, topic_of: dict[tuple[str, str], str], thresholds: list[float]) -> dict[str, object]:
    """Replay month-to-month matching on the stored clusters at each threshold (no re-clustering).

    A cluster's "true topic" is its members' majority label. For each cluster after the first month:
    correct = linked to a previous cluster with the same true topic; wrong = linked to a different one;
    missed = left unlinked although that true topic existed last month; new_ok = unlinked, and truly new.
    """
    by_period = dominant_labels(org, topic_of)
    periods = sorted(by_period)

    # One record per cluster after the first month: its best match last month, and what it should be.
    pairs = []
    for prev_p, cur_p in zip(periods, periods[1:]):
        previous = by_period[prev_p]
        for cluster, label in by_period[cur_p]:
            scored = [(trends.cosine(cluster.centroid, p.centroid), p_label) for p, p_label in previous]
            best_score, best_label = max(scored)
            pairs.append({
                "period": cur_p, "label": label, "size": cluster.query_count,
                "best_score": best_score, "best_label": best_label,
                "existed": any(p_label == label for _, p_label in scored),
                "same": max((s for s, p_label in scored if p_label == label), default=None),
                "different": max((s for s, p_label in scored if p_label != label), default=0.0),
            })  # fmt: skip

    results: dict[str, object] = {}
    for t in thresholds:
        tally: Counter[str] = Counter()
        emerging: Counter[str] = Counter()  # unlinked and big enough: what the batch would call "emerging"
        for p in pairs:
            if p["best_score"] >= t:
                tally["correct" if p["best_label"] == p["label"] else "wrong"] += 1
            else:
                tally["missed" if p["existed"] else "new_ok"] += 1
                emerging[p["period"]] += p["size"] >= settings.hdbscan_min_cluster_size
        results[str(t)] = {**tally, "emerging_per_month": dict(emerging)}
        print(f"  threshold {t:.2f}: " + "  ".join(f"{k}={v}" for k, v in results[str(t)].items()))

    same = [p["same"] for p in pairs if p["same"] is not None]
    different = [p["different"] for p in pairs]

    def quartiles(xs: list[float]) -> str:
        q = np.percentile(xs, [0, 25, 50, 75, 100])
        return " / ".join(f"{v:.3f}" for v in q)

    print(f"\n  best similarity to the SAME true topic last month   (min/25%/median/75%/max): {quartiles(same)}")
    print(f"  best similarity to a DIFFERENT true topic last month (min/25%/median/75%/max): {quartiles(different)}")
    results["similarity_same_topic"] = sorted(round(s, 4) for s in same)
    results["similarity_different_topic"] = sorted(round(s, 4) for s in different)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[4, 6, 8, 10])
    parser.add_argument(
        "--match-thresholds", type=float, nargs="+",
        help="instead of re-clustering, replay topic matching on the stored clusters at these thresholds",
    )  # fmt: skip
    args = parser.parse_args()
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    topic_of = {(item["period"], item["text"]): item["topic"] for item in labels}

    if args.match_thresholds:
        print(f"topic matching on stored clusters (min_cluster_size={settings.hdbscan_min_cluster_size})")
        out = LABELS_PATH.parent / "matching.json"
        out.write_text(json.dumps(evaluate_matching(args.org, topic_of, args.match_thresholds), indent=2), encoding="utf-8")
        print(f"\nsaved {out}")
        return

    results = {}
    for size in args.sizes:
        settings.hdbscan_min_cluster_size = size
        with SessionLocal() as db:
            run_analysis(db, args.org)
        results[size] = evaluate(args.org, topic_of)
        print(f"\nmin_cluster_size = {size}")
        for row in results[size]:
            print("  " + "  ".join(f"{k}={v}" for k, v in row.items()))
    out = LABELS_PATH.parent / "tuning.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
