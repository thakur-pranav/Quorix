"""Index a website for an organization from the terminal (same pipeline as POST /api/sources).

Usage (from backend/):
    python -m scripts.index_site https://docs.github.com/en/billing --org org_demo
Re-running for the same URL and org re-indexes it (replaces chunks).
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.ingest import pipeline
from app.ingest.ssrf import assert_public_url
from app.models import Source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("--org", required=True, help="organization id, e.g. org_demo")
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    assert_public_url(args.url)
    Base.metadata.create_all(engine)  # dev convenience, same as the app's lifespan

    with SessionLocal() as db:
        source = db.scalar(
            select(Source).where(Source.organization_id == args.org, Source.location == args.url)
        )
        if source is None:
            source = Source(
                organization_id=args.org, kind="website", label=args.label or args.url, location=args.url
            )
            db.add(source)
            db.commit()
        source_id = source.id

    started = time.time()
    pipeline.run_ingestion(source_id, args.org)

    with SessionLocal() as db:
        done = db.get(Source, source_id)
        assert done is not None
        print(
            f"{done.status}: {done.page_count} pages, {done.chunk_count} chunks "
            f"in {time.time() - started:.0f}s (source {done.id}, org {args.org})"
        )
        if done.error:
            print(f"error: {done.error}")


if __name__ == "__main__":
    main()
