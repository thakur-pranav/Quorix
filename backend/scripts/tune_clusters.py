"""Tune HDBSCAN's min_cluster_size on seeded data (ROADMAP Day 5).

For each candidate size: run the full batch for every period, then measure
- topics and noise % per period,
- against the true topic labels written by seed_conversations.py (noise counts as its own group):
  homogeneity (is each cluster about ONE topic? what makes a topic actionable),
  completeness (does each topic stay in ONE cluster? what keeps trends stable) and
  ARI (overall agreement, 1.0 = identical grouping, 0 = chance; it punishes splitting a topic
  into pure sub-topics as hard as mixing topics, so it understates quality here),
- whether the planted trends were caught: the growing topic should be "emerging" in the last
  two months, and the fading topic "declining" in the middle month.

Run it with LLM_PROVIDER=none so names and severity use the free fallbacks; clustering doesn't
depend on them. Usage (from backend/):
    LLM_PROVIDER=none python -m scripts.tune_clusters --org org_demo --sizes 4 6 8 10
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sklearn.metrics import adjusted_rand_score, homogeneity_completeness_v_measure
from sqlalchemy import select

from app.analytics.batch import run_all_periods
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[4, 6, 8, 10])
    args = parser.parse_args()
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    topic_of = {(item["period"], item["text"]): item["topic"] for item in labels}

    results = {}
    for size in args.sizes:
        settings.hdbscan_min_cluster_size = size
        with SessionLocal() as db:
            run_all_periods(db, args.org)
        results[size] = evaluate(args.org, topic_of)
        print(f"\nmin_cluster_size = {size}")
        for row in results[size]:
            print("  " + "  ".join(f"{k}={v}" for k, v in row.items()))
    out = LABELS_PATH.parent / "tuning.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
