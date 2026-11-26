"""Run the evaluation on the committed question set and write the numbers for EXPERIMENTS.md.

Four parts:
1. Retrieval, no LLM: hit rate@1/3/5/8 and MRR over every answerable question (was the source
   section retrieved, and how high?). Free and deterministic.
2. The stored run at the configured top_k: the three judged metrics on the answerable questions,
   saved as an EvaluationRun (what the Evaluation page shows).
3. Optional --top-k experiment: the judged metrics at other k on a subset (--experiment-size),
   since every k needs new answers and new judgements.
4. Confidence: the low-confidence threshold re-check (answerable vs unanswerable), and whether
   low confidence goes with low faithfulness.

Per-question results go to docs/experiments/evaluation.json. Usage (from backend/):
    python -m scripts.run_evaluation --org org_demo
    python -m scripts.run_evaluation --org org_demo --top-k 3 5 8 --experiment-size 30
    python -m scripts.run_evaluation --org org_demo --top-k 3 8 --experiment-only   # just part 3
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from scipy.stats import spearmanr
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.evaluation import METRICS, QuestionResult, evaluate_question, run_evaluation
from app.rag import engine

EVAL_SET_PATH = Path(__file__).parent / "data" / "eval_set.json"
OUT_PATH = Path(__file__).resolve().parents[2] / "docs" / "experiments" / "evaluation.json"
HIT_KS = (1, 3, 5, 8)
THRESHOLDS = (0.35, 0.40, 0.45, 0.48, 0.51, 0.55)


def retrieval_metrics(db: Session, org: str, items: list[dict]) -> dict[str, float]:
    """Hit rate@k and MRR from ONE top-8 retrieval per question (a top-k list is a prefix of top-8)."""
    ranks: list[int | None] = []
    for item in items:
        hits = engine.retrieve_only(db, item["question"], org, max(HIT_KS))
        source = (item["source_url"], item["source_heading"])
        ranks.append(next((n for n, h in enumerate(hits, start=1) if (h.url, h.heading_path) == source), None))
    out = {f"hit@{k}": round(sum(r is not None and r <= k for r in ranks) / len(ranks), 3) for k in HIT_KS}
    out["mrr@8"] = round(sum(1 / r for r in ranks if r) / len(ranks), 3)  # mean reciprocal rank
    return out


def summary(results: list[QuestionResult]) -> dict[str, object]:
    answered = [r for r in results if r.answer is not None]

    def mean(metric: str) -> float | None:
        scores = [s for r in answered if (s := r.scores[metric]) is not None]
        return round(statistics.mean(scores), 3) if scores else None

    return {
        "answered": len(answered),
        "skipped": len(results) - len(answered),
        **{m: mean(m) for m in METRICS},
        "failed_judgements": sum(r.scores[m] is None for r in answered for m in METRICS),
    }


def threshold_table(answerable: list[QuestionResult], unanswerable: list[QuestionResult]) -> list[dict[str, float]]:
    """At each threshold: answerable questions refused (bad) vs unanswerable ones let through."""
    return [
        {
            "threshold": t,
            "answerable_refused": round(sum(r.confidence < t for r in answerable) / len(answerable), 3),
            "unanswerable_passed": round(sum(r.confidence >= t for r in unanswerable) / max(1, len(unanswerable)), 3),
        }
        for t in THRESHOLDS
    ]


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation: does higher confidence go with higher faithfulness? Ranks, not values,
    so it doesn't assume a straight-line relationship. None if there's too little to say."""
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    return round(float(spearmanr(xs, ys).statistic), 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    parser.add_argument("--top-k", type=int, nargs="*", default=[], help="extra k values for the experiment")
    parser.add_argument("--experiment-size", type=int, default=30, help="answerable questions per extra k")
    parser.add_argument("--experiment-only", action="store_true", help="skip parts 1, 2 and 4; merge into the saved report")
    args = parser.parse_args()
    if settings.llm_provider == "none":
        raise SystemExit("configure an LLM provider in backend/.env first")

    items = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))["questions"]
    answerable = [i for i in items if i["answerable"]]
    unanswerable = [i for i in items if not i["answerable"]]
    report: dict[str, object] = {"judge_model": settings.judge_model, "generator_model": settings.groq_model}
    if args.experiment_only:
        report = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    with SessionLocal() as db:
        k = settings.retrieval_top_k
        results: list[QuestionResult] = []
        if not args.experiment_only:
            report["retrieval"] = retrieval_metrics(db, args.org, answerable)
            print("retrieval:", report["retrieval"])

            run, results = run_evaluation(db, args.org, [i["question"] for i in answerable])
            off_topic = [evaluate_question(db, i["question"], args.org) for i in unanswerable]
            report["stored_run"] = {"id": run.id, "top_k": k, **summary(results)}
            report["unanswerable"] = summary(off_topic)
            print(f"top_k={k} (stored as {run.id}):", report["stored_run"])
            print("unanswerable:", report["unanswerable"])

            report["thresholds"] = threshold_table(results, off_topic)
            pairs = [(r.confidence, f) for r in results if (f := r.scores.get("faithfulness")) is not None]
            report["confidence_vs_faithfulness_spearman"] = spearman([c for c, _ in pairs], [f for _, f in pairs])
            print("thresholds:", report["thresholds"])
            print("confidence vs faithfulness (Spearman):", report["confidence_vs_faithfulness_spearman"])
            report["per_question"] = [{**asdict(r), "answerable": True} for r in results] + [
                {**asdict(r), "answerable": False} for r in off_topic
            ]

        experiment: dict[str, object] = {}
        subset = [i["question"] for i in answerable[: args.experiment_size]]
        for extra_k in sorted(set(args.top_k)):
            if extra_k == k and results:  # reuse the stored run's answers for the same subset
                rows = [r for r in results if r.question in set(subset)]
            else:
                rows = [evaluate_question(db, q, args.org, extra_k) for q in subset]
            experiment[str(extra_k)] = summary(rows)
            print(f"experiment top_k={extra_k}:", experiment[str(extra_k)])
        if experiment:  # merge: an --experiment-only re-run keeps the other k values' rows
            previous = report.get("top_k_experiment", {}).get("results", {})  # type: ignore[union-attr]
            report["top_k_experiment"] = {"questions": len(subset), "results": {**previous, **experiment}}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {OUT_PATH}")


if __name__ == "__main__":
    main()
