"""Copy the finished demo organization from the local database into another one (production).

The demo (indexed docs with their vectors, seeded conversations, topics, reports, the evaluation
run) was built locally. Copying the rows is exact, takes seconds and needs no LLM; rebuilding on
the server would re-crawl, re-seed and re-run the analysis with slightly different results.

- One organization only (`--org`, default org_demo): other local orgs (tests, experiments) stay.
- Re-runnable: the org's rows in the target are deleted first (children before parents).
- Auto-increment ids (cluster_members) are NOT copied: the target database numbers them, so
  its sequence stays correct for future inserts. String ids (src_…, msg_…) are kept.
- The target URL comes from the environment, never the command line (shell history):
    TARGET_DATABASE_URL=postgresql+psycopg://... python -m scripts.bootstrap_demo
  The target must already be migrated (`alembic upgrade head`).
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import Table, create_engine, delete, func, insert, inspect, select

from app import models  # noqa: F401  (registers the tables)
from app.db import Base, engine as source_engine

BATCH = 500


def copy_org(org: str, target_url: str) -> dict[str, int]:
    target = create_engine(target_url)
    missing = set(Base.metadata.tables) - set(inspect(target).get_table_names())
    if missing:
        raise SystemExit(f"target is missing tables {sorted(missing)}: run `alembic upgrade head` on it first")

    tables: list[Table] = list(Base.metadata.sorted_tables)  # parents before children
    copied: dict[str, int] = {}
    with source_engine.connect() as src, target.begin() as dst:  # one transaction: all or nothing
        for table in reversed(tables):  # children first, so foreign keys never block a delete
            dst.execute(delete(table).where(table.c.organization_id == org))
        for table in tables:
            auto_id = table.autoincrement_column  # e.g. cluster_members.id: let the target number it
            columns = [c for c in table.columns if c is not auto_id]
            rows = [dict(r._mapping) for r in src.execute(select(*columns).where(table.c.organization_id == org))]
            for start in range(0, len(rows), BATCH):
                dst.execute(insert(table), rows[start : start + BATCH])
            copied[table.name] = len(rows)

        # Check: the target now holds exactly what the source has, table by table.
        for table in tables:
            n = dst.scalar(select(func.count()).select_from(table).where(table.c.organization_id == org))
            if n != copied[table.name]:
                raise RuntimeError(f"{table.name}: copied {copied[table.name]} rows but the target has {n}")
    target.dispose()
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", default="org_demo")
    args = parser.parse_args()
    target_url = os.environ.get("TARGET_DATABASE_URL")
    if not target_url:
        raise SystemExit("set TARGET_DATABASE_URL (the production database) in the environment")
    if target_url == str(source_engine.url.render_as_string(hide_password=False)):
        raise SystemExit("the target is the same database as the source")
    for table, n in copy_org(args.org, target_url).items():
        print(f"{n:5}  {table}")
    print(f"copied {args.org}: done (verified row counts)")


if __name__ == "__main__":
    main()
