"""Database engine, session factory, declarative base and the get_db() dependency."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


def _engine_kwargs(url: str) -> dict[str, Any]:
    if not url.startswith("sqlite"):
        # Postgres: test pooled connections before use, so a dropped connection doesn't fail a request.
        return {"pool_pre_ping": True}

    # SQLite: FastAPI may use a connection from a different thread than the one that created it.
    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    db_path = make_url(url).database
    if db_path in (None, "", ":memory:"):
        # In-memory DB exists per connection, so every session must share one connection.
        kwargs["poolclass"] = StaticPool
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return kwargs


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))

if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        # SQLite ignores foreign keys (and ON DELETE CASCADE) unless this is set on every connection.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Parent class of every ORM model in app/models.py."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Shorthand for route signatures: `def list_sources(db: DbSession, ...)`.
DbSession = Annotated[Session, Depends(get_db)]
