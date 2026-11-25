"""Measure the low-confidence threshold (ROADMAP Day 3, SPEC section 6.5).

For each labelled question (covered by the docs = 1, not covered = 0), compute the retrieval
confidence exactly as chat does (no LLM, nothing logged), then find the threshold that best
separates the two groups.

Usage (from backend/):
    python -m scripts.measure_threshold --org org_demo --out ../docs/experiments/threshold.csv
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from app.rag.engine import compute_confidence, retrieve_only

DEFAULT_QUESTIONS = Path(__file__).parent / "data" / "threshold_questions.csv"


@dataclass(frozen=True)
class Row:
    question: str
    covered: bool
    confidence: float
    best: float
    top_section: str


def measure(questions: Path, org: str) -> list[Row]:
    rows = []
    with questions.open(encoding="utf-8") as f:
        for item in csv.DictReader(f):
            hits = retrieve_only(item["question"], org)
            scores = [h.similarity for h in hits]
            rows.append(
                Row(
                    question=item["question"],
                    covered=item["covered"] == "1",
                    confidence=compute_confidence(scores),
                    best=max(scores, default=0.0),
                    top_section=hits[0].heading_path if hits else "",
                )
            )
    return rows


def best_threshold(rows: list[Row]) -> tuple[float, int]:
    """Threshold with the most correct calls (covered >= t, not covered < t).

    Candidates are midpoints between neighbouring scores. Ties go to the widest gap, so the
    chosen value sits as far as possible from the nearest question on either side.
    """
    values = sorted({r.confidence for r in rows})
    candidates = [(a + b) / 2 for a, b in zip(values, values[1:], strict=False)] or values

    def correct(t: float) -> int:
        return sum((r.confidence >= t) == r.covered for r in rows)

    def gap(t: float) -> float:
        below = max((v for v in values if v < t), default=t)
        above = min((v for v in values if v >= t), default=t)
        return above - below

    chosen = max(candidates, key=lambda t: (correct(t), gap(t)))
    return round(chosen, 2), correct(chosen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out", type=Path, required=True, help="results CSV to write")
    args = parser.parse_args()

    rows = measure(args.questions, args.org)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "covered", "confidence", "best_similarity", "top_section"])
        for r in sorted(rows, key=lambda r: -r.confidence):
            writer.writerow([r.question, int(r.covered), r.confidence, round(r.best, 4), r.top_section])

    covered = sorted(r.confidence for r in rows if r.covered)
    other = sorted(r.confidence for r in rows if not r.covered)
    threshold, correct = best_threshold(rows)
    print(f"covered     (n={len(covered)}): min {covered[0]:.3f}  median {covered[len(covered) // 2]:.3f}  max {covered[-1]:.3f}")
    print(f"not covered (n={len(other)}): min {other[0]:.3f}  median {other[len(other) // 2]:.3f}  max {other[-1]:.3f}")
    print(f"best threshold: {threshold}  ->  {correct}/{len(rows)} correct")
    for r in sorted(rows, key=lambda r: -r.confidence):
        wrong = "  <-- WRONG SIDE" if (r.confidence >= threshold) != r.covered else ""
        label = "covered" if r.covered else "off    "
        print(f"  {r.confidence:.3f}  {label}  {r.question[:60]}{wrong}")
    print(f"results written to {args.out}")


if __name__ == "__main__":
    main()
