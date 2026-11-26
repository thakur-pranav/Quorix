"""Migrations: they apply cleanly, match the models exactly, and roll back.

The other tests build tables with create_all (fast). This test is what keeps that honest: if
someone changes app/models.py without writing a migration, the diff below is non-empty and CI
fails ("schema drift").
"""

from __future__ import annotations

from pathlib import Path

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


def test_migrations_match_the_models_and_roll_back(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
    assert diff == [], f"models and migrations differ: write a migration ({diff})"
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
