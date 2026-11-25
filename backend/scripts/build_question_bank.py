"""Generate the seed question bank once with the LLM, from the org's real indexed docs.

For each chosen doc topic, the LLM reads that topic's passages and writes varied, realistic
customer questions. Off-topic ("unanswerable") questions are generated separately. The result
is saved as JSON and committed, so seeding is reproducible and never calls the LLM again.

Usage (from backend/, LLM configured in .env):
    python -m scripts.build_question_bank --org org_demo
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app import llm
from app.config import settings
from app.db import SessionLocal
from app.models import Chunk

BANK_PATH = Path(__file__).parent / "data" / "seed_questions.json"

# (doc article title, role, how many questions to generate)
TOPICS: list[tuple[str, str, int]] = [
    ("Troubleshooting a declined credit card charge", "growing", 55),
    ("Payments for customers in India", "fading", 55),
    ("Unlocking a locked account", "steady", 30),
    ("Managing your payment and billing information", "steady", 30),
    ("Billing cycles", "steady", 30),
    ("Upgrading your account's plan", "steady", 30),
    ("Downgrading your account's plan", "steady", 30),
    ("GitHub Actions billing", "steady", 30),
    ("GitHub Codespaces billing", "steady", 30),
    ("Git Large File Storage billing", "steady", 30),
    ("GitHub Copilot licenses", "steady", 30),
    ("Setting up budgets to control spending on metered products", "steady", 30),
    ("Troubleshooting authorization holds", "steady", 30),
    ("Canceling a GitHub Marketplace app", "steady", 30),
    ("GitHub Packages billing", "steady", 30),
    ("Managing invoices for your enterprise", "steady", 30),
]
UNANSWERABLE_COUNT = 70
MAX_CONTEXT_WORDS = 1400
PAUSE_SECONDS = 2.0  # stay well inside the free tier's requests-per-minute limit

SYSTEM = """You generate realistic customer support questions for testing a help-desk system. \
Write like real customers: first person, varied length (4 to 30 words), varied tone (calm, \
confused, frustrated, in a hurry), some with context about their situation, a few with small \
typos or missing punctuation. Every question must be different in wording, not just a synonym \
swap. No numbering, no answers. Reply with JSON only: {"questions": ["...", "..."]}"""


def _passages(org: str, title: str) -> str:
    with SessionLocal() as db:
        chunks = db.scalars(
            select(Chunk).where(Chunk.organization_id == org, Chunk.heading_path.startswith(title)).order_by(Chunk.id)
        ).all()
    words: list[str] = []
    for chunk in chunks:
        words.extend(chunk.text.split())
        if len(words) >= MAX_CONTEXT_WORDS:
            break
    if not words:
        raise SystemExit(f"no indexed passages for topic {title!r} in {org}")
    return " ".join(words[:MAX_CONTEXT_WORDS])


def _questions(user: str, wanted: int) -> list[str]:
    data = llm.complete_json(user, SYSTEM, temperature=0.9, max_tokens=6000)
    raw = data.get("questions")
    if not isinstance(raw, list):
        raise llm.LLMError("no 'questions' list in the reply")
    seen: set[str] = set()
    questions = []
    for item in raw:
        if isinstance(item, str) and 3 <= len(item.split()) <= 60 and item.strip().lower() not in seen:
            seen.add(item.strip().lower())
            questions.append(item.strip())
    if len(questions) < wanted * 0.7:
        raise llm.LLMError(f"only {len(questions)} usable questions, wanted {wanted}")
    return questions[:wanted]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    args = parser.parse_args()
    if settings.llm_provider == "none":
        raise SystemExit("configure an LLM provider in backend/.env first")

    bank: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": settings.groq_model or settings.gemini_model,
        "source": "GitHub Docs, Billing section (https://docs.github.com/en/billing)",
        "topics": [],
    }
    for title, role, wanted in TOPICS:
        user = (
            f"Topic: {title}\n\nDocumentation passages:\n{_passages(args.org, title)}\n\n"
            f"Write {wanted} different questions that customers would send to support about this topic, "
            "which these passages can answer."
        )
        questions = _questions(user, wanted)
        bank["topics"].append({"topic": title, "role": role, "questions": questions})  # type: ignore[union-attr]
        print(f"{len(questions):3}  {role:7}  {title}")
        time.sleep(PAUSE_SECONDS)

    user = (
        f"Write {UNANSWERABLE_COUNT} different questions that GitHub customers might send to a BILLING "
        "help desk that are NOT about billing, payments, plans, licenses or usage costs: for example "
        "passwords, two-factor authentication, repositories, pull requests, SSH keys, notifications, "
        "GitHub Pages, account deletion, plus a few unrelated to GitHub entirely."
    )
    unanswerable = _questions(user, UNANSWERABLE_COUNT)
    bank["unanswerable"] = unanswerable
    print(f"{len(unanswerable):3}  unanswerable")

    BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    BANK_PATH.write_text(json.dumps(bank, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {BANK_PATH}")


if __name__ == "__main__":
    main()
