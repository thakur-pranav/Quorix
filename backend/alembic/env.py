"""Alembic environment: how `alembic upgrade` and `alembic revision --autogenerate` connect.

- The URL comes from app settings (DATABASE_URL), never from alembic.ini: no secret in git.
- `target_metadata` is the app's models, so autogenerate diffs the models against the database.
- SQLite can't ALTER most things, so `render_as_batch` makes Alembic copy-and-swap tables there;
  on Postgres the same migration runs as plain ALTERs.
"""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import DateTime, engine_from_config, pool

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.config import settings
from app.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tests pass their own URL via config.attributes; everything else uses the app's setting.
url = config.attributes.get("database_url") or settings.database_url
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # % is ini interpolation syntax

target_metadata = Base.metadata


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    """Write UTCDateTime as its underlying DateTime(timezone=True) in migrations.

    Migrations must not import app code: a later refactor of app/models.py would break every
    old migration file. The UTC conversion is Python-side anyway; the column is a plain timestamp.
    """
    if type_ == "type" and type(obj).__name__ == "UTCDateTime":
        return repr(DateTime(timezone=True)).replace("DateTime", "sa.DateTime")
    return False  # default rendering for everything else


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it (for review)."""
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        render_as_batch=True, render_item=render_item, compare_type=True,
    )  # fmt: skip
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite", render_item=render_item, compare_type=True,
        )  # fmt: skip
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
