"""Build the evaluation question set once with the LLM, from the org's indexed docs (SPEC section 8).

- Answerable: pick random passages (one per section, spread over the docs) and have the LLM write
  ONE customer question each passage answers. Each item keeps its source (page URL + section
  heading), so retrieval can be scored without a judge: was the right section in the top k?
  (hit rate@k). URL + heading, not the chunk id: ids are random and change on re-indexing.
- Unanswerable (~20%): questions the docs don't cover, written from the list of the docs'
  section titles so they're plausible for THIS help center. Labelled, for the confidence
  threshold re-check.

Saved as committed JSON, so evaluation is reproducible and never regenerates questions. Separate
from the seeding bank (scripts/data/seed_questions.json): evaluation must not test on the data
the analytics were tuned on. Usage (from backend/, LLM configured in .env):
    python -m scripts.build_eval_set --org org_demo
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app import llm
from app.config import settings
from app.db import SessionLocal
from app.models import Chunk

EVAL_SET_PATH = Path(__file__).parent / "data" / "eval_set.json"
MIN_PASSAGE_WORDS = 60  # shorter chunks are navigation or fragments: nothing to ask about
MAX_SECTION_TITLES = 80

ANSWERABLE_SYSTEM = """You write test questions for a customer support assistant. Given ONE \
documentation passage, write ONE question a real customer could ask that this passage answers \
fully. Write like a customer (first person, plain words, 6 to 25 words); don't copy phrases \
from the passage. Reply with JSON only: {"question": "..."}"""

UNANSWERABLE_SYSTEM = """You write test questions for a customer support assistant. Given the \
section titles of a help center, write questions its customers might plausibly send that this \
documentation would NOT answer: related products or account areas it doesn't cover, policies it \
doesn't mention, and a few unrelated to the product. Write like customers, 6 to 25 words, all \
different. Reply with JSON only: {"questions": ["...", "..."]}"""


def sample_passages(org: str, n: int, rng: random.Random) -> list[Chunk]:
    """n substantial passages, at most one per section, in a reproducible random order."""
    with SessionLocal() as db:
        chunks = list(db.scalars(select(Chunk).where(Chunk.organization_id == org).order_by(Chunk.id)))
    rng.shuffle(chunks)
    picked, seen = [], set()
    for chunk in chunks:
        key = (chunk.url, chunk.heading_path)
        if chunk.word_count >= MIN_PASSAGE_WORDS and key not in seen:
            seen.add(key)
            picked.append(chunk)
        if len(picked) == n:
            break
    if len(picked) < n:
        raise SystemExit(f"only {len(picked)} substantial passages in {org}; asked for {n}")
    return picked


def answerable_question(chunk: Chunk) -> str | None:
    try:
        data = llm.complete_json(f"Section: {chunk.heading_path}\n\nPassage:\n{chunk.text}", ANSWERABLE_SYSTEM, temperature=0.7)
    except llm.LLMError as exc:
        print(f"  skipped {chunk.heading_path[:60]!r}: {exc}")
        return None
    question = str(data.get("question", "")).strip()
    return question if 3 <= len(question.split()) <= 60 else None


def unanswerable_questions(org: str, n: int) -> list[str]:
    with SessionLocal() as db:
        titles = sorted({h.split(" › ")[0] for h in db.scalars(select(Chunk.heading_path).where(Chunk.organization_id == org)) if h})
    user = "Section titles:\n" + "\n".join(f"- {t}" for t in titles[:MAX_SECTION_TITLES]) + f"\n\nWrite {n} questions."
    data = llm.complete_json(user, UNANSWERABLE_SYSTEM, temperature=0.9, max_tokens=4000)
    raw = data.get("questions")
    if not isinstance(raw, list):
        raise llm.LLMError("no 'questions' list in the reply")
    unique = list(dict.fromkeys(q.strip() for q in raw if isinstance(q, str) and 3 <= len(q.split()) <= 60))
    return unique[:n]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    parser.add_argument("--answerable", type=int, default=60)
    parser.add_argument("--unanswerable", type=int, default=15)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    if settings.llm_provider == "none":
        raise SystemExit("configure an LLM provider in backend/.env first")

    rng = random.Random(args.seed)
    items: list[dict[str, object]] = []
    for chunk in sample_passages(args.org, args.answerable, rng):
        question = answerable_question(chunk)
        if question:
            items.append({"question": question, "answerable": True, "source_url": chunk.url,
                          "source_heading": chunk.heading_path})  # fmt: skip
            print(f"{len(items):3}  {question}")
    for question in unanswerable_questions(args.org, args.unanswerable):
        items.append({"question": question, "answerable": False, "source_url": None, "source_heading": None})
    for n, item in enumerate(items, start=1):
        item["id"] = f"q{n:03d}"

    EVAL_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVAL_SET_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model": settings.groq_model or settings.gemini_model,
                "org": args.org,
                "seed": args.seed,
                "questions": items,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    answerable = sum(1 for i in items if i["answerable"])
    print(f"saved {EVAL_SET_PATH}: {answerable} answerable + {len(items) - answerable} unanswerable")


if __name__ == "__main__":
    main()
