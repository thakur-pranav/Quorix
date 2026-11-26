"""Migrations: they apply cleanly, match the models exactly, and roll back.

The other tests build tables with create_all (fast). This test is what keeps that honest: if
someone changes app/models.py without writing a migration, the diff below is non-empty and CI
fails ("schema drift").
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db import Base

BACKEND = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.attributes["database_url"] = url  # env.py prefers this over settings
    return config


def database_urls() -> list[str]:
    """SQLite always; Postgres too when CI provides an empty database for it."""
    urls = ["sqlite"]
    if os.environ.get("TEST_MIGRATIONS_DATABASE_URL"):
        urls.append(os.environ["TEST_MIGRATIONS_DATABASE_URL"])
    return urls


@pytest.mark.parametrize("target", database_urls(), ids=lambda u: u.split(":")[0])
def test_migrations_match_the_models_and_roll_back(tmp_path: Path, target: str) -> None:
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}" if target == "sqlite" else target
    config = alembic_config(url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
    assert diff == [], f"models and migrations differ: write a migration ({diff})"
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    with engine.begin() as connection:  # leave the database as empty as it started
        connection.exec_driver_sql("DROP TABLE alembic_version")
    engine.dispose()
