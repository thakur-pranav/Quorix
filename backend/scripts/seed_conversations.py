"""Seed three months of customer questions for an org, from the committed question bank.

Plan C (docs/NOTES.md, Day 5):
- Past months: each question goes through `record_question`, the SAME retrieval and confidence
  code as live chat, dated into that month. No LLM answers (analytics never reads them).
- Current month: the same, plus `--live N` questions sent through the real POST /api/chat
  endpoint (real LLM answers) on a running backend.
Every seeded conversation is flagged synthetic=True. Planted patterns: a growing topic
(5 → 15 → 40), a fading topic (40 → 15 → 5) and ~10% questions the docs can't answer.

Usage (from backend/):
    python -m scripts.seed_conversations --org org_demo --reset
    python -m scripts.seed_conversations --org org_demo --live 30   # needs the API on :8000
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from sqlalchemy import delete, select, update

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Conversation, Report, TopicCluster
from app.rag import engine as rag

BANK_PATH = Path(__file__).parent / "data" / "seed_questions.json"
LABELS_PATH = Path(__file__).resolve().parents[2] / "docs" / "experiments" / "seed_labels.json"
COUNTS = {"growing": (5, 15, 40), "fading": (40, 15, 5)}
STEADY_RANGE = (9, 17)
UNANSWERABLE_SHARE = 0.10
LIVE_PAUSE_SECONDS = 3.0
SESSION_PREFIX = "seed-"


@dataclass(frozen=True)
class Planned:
    period: str
    topic: str  # bank topic title, or "unanswerable"
    text: str


def month_starts(today: datetime, months: int) -> list[datetime]:
    """The first instant of the last `months` months, oldest first (current month last)."""
    starts, year, month = [], today.year, today.month
    for _ in range(months):
        starts.append(datetime(year, month, 1, tzinfo=timezone.utc))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return list(reversed(starts))


def plan(bank: dict, periods: list[str], rng: random.Random) -> list[Planned]:
    planned: list[Planned] = []
    for p, period in enumerate(periods):
        in_period: list[Planned] = []
        for topic in bank["topics"]:
            counts = COUNTS.get(topic["role"])
            n = counts[p] if counts else rng.randint(*STEADY_RANGE)
            in_period += [Planned(period, topic["topic"], q) for q in rng.sample(topic["questions"], n)]
        n_off = round(len(in_period) * UNANSWERABLE_SHARE / (1 - UNANSWERABLE_SHARE))
        in_period += [Planned(period, "unanswerable", q) for q in rng.sample(bank["unanswerable"], n_off)]
        rng.shuffle(in_period)
        planned += in_period
    return planned


def conversations(items: list[Planned], rng: random.Random) -> list[list[Planned]]:
    """Group a period's questions into conversations of 1–3 questions."""
    groups, i = [], 0
    while i < len(items):
        size = rng.choice((1, 1, 1, 2, 2, 3))
        groups.append(items[i : i + size])
        i += size
    return groups


def random_time(start: datetime, end: datetime, rng: random.Random) -> datetime:
    return start + timedelta(seconds=rng.uniform(0, (end - start).total_seconds()))


def reset(org: str) -> None:
    with SessionLocal() as db:
        db.execute(delete(TopicCluster).where(TopicCluster.organization_id == org))
        db.execute(delete(Report).where(Report.organization_id == org))
        db.execute(delete(Conversation).where(Conversation.organization_id == org, Conversation.synthetic.is_(True)))
        db.commit()
    print(f"reset: removed synthetic conversations, topics and reports for {org}")


def seed_history(org: str, items: list[Planned], period_bounds: dict[str, tuple[datetime, datetime]], rng: random.Random) -> list[dict[str, str]]:
    labels = []
    with SessionLocal() as db:
        for period in period_bounds:
            for group in conversations([q for q in items if q.period == period], rng):
                session = f"{SESSION_PREFIX}{rng.getrandbits(48):012x}"
                at = random_time(*period_bounds[period], rng)
                for q in group:
                    rag.record_question(db, org, session, q.text, asked_at=at, synthetic=True)
                    labels.append({"period": period, "topic": q.topic, "text": q.text})
                    at += timedelta(minutes=rng.randint(1, 6))
    return labels


def seed_live(org: str, items: list[Planned], api: str) -> list[dict[str, str]]:
    """Send questions through the real chat endpoint (real LLM answers), then flag them synthetic."""
    now = int(time.time())
    token = jwt.encode(
        {"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": "seed-script", "org": org,
         "email": "seed@quorix.local", "iat": now, "exp": now + 3600},  # one token for the run
        settings.backend_jwt_secret, algorithm=settings.jwt_algorithm,
    )  # fmt: skip
    labels, low = [], 0
    with httpx.Client(base_url=api, headers={"Authorization": f"Bearer {token}"}, timeout=120) as client:
        for n, q in enumerate(items, start=1):
            res = client.post("/api/chat", json={"question": q.text, "sessionId": f"{SESSION_PREFIX}live-{n:03d}"})
            res.raise_for_status()
            low += res.json()["lowConfidence"]
            labels.append({"period": q.period, "topic": q.topic, "text": q.text})
            print(f"  live {n}/{len(items)} confidence={res.json()['confidence']:.2f}")
            time.sleep(LIVE_PAUSE_SECONDS)
    with SessionLocal() as db:
        db.execute(
            update(Conversation)
            .where(Conversation.organization_id == org, Conversation.session_id.startswith(f"{SESSION_PREFIX}live-"))
            .values(synthetic=True)
        )
        db.commit()
    print(f"live: {len(items)} questions through /api/chat ({low} refused as low confidence)")
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    parser.add_argument("--reset", action="store_true", help="delete this org's synthetic history first")
    parser.add_argument("--live", type=int, default=0, help="also send N current-month questions via the API")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    if args.reset:
        reset(args.org)
    rng = random.Random(args.seed)
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))

    now = datetime.now(timezone.utc)
    starts = month_starts(now, 3)
    periods = [s.strftime("%Y-%m") for s in starts]
    bounds = {periods[0]: (starts[0], starts[1]), periods[1]: (starts[1], starts[2]), periods[2]: (starts[2], now)}
    items = plan(bank, periods, rng)

    live_items = [q for q in items if q.period == periods[2]][: args.live]
    history = [q for q in items if q not in live_items]
    started = time.time()
    labels = seed_history(args.org, history, bounds, rng)
    print(f"history: {len(history)} questions logged in {time.time() - started:.0f}s")
    if live_items:
        labels += seed_live(args.org, live_items, args.api)

    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(json.dumps(labels, indent=1, ensure_ascii=False), encoding="utf-8")
    per_period = Counter(q.period for q in items)
    print("per period:", dict(per_period))
    for role in ("growing", "fading"):
        topic = next(t["topic"] for t in bank["topics"] if t["role"] == role)
        print(f"  {role:8} {topic}: {[sum(1 for q in items if q.topic == topic and q.period == p) for p in periods]}")
    print(f"labels written to {LABELS_PATH}")

    with SessionLocal() as db:
        synthetic = db.scalar(select(Conversation.id).where(Conversation.organization_id == args.org, Conversation.synthetic.is_(False)).limit(1))
        if synthetic:
            print("note: this org also has real (non-synthetic) conversations; they are kept")


if __name__ == "__main__":
    main()
