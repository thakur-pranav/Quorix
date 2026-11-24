"""Shared test setup. Runs before any test module imports the app."""

from __future__ import annotations

import os

# Must be set before `app.config` is imported, because `settings = Settings()` runs at import.
TEST_JWT_SECRET = "test-secret-that-is-definitely-longer-than-32-chars"
os.environ["BACKEND_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


# Imports below the env setup on purpose: app modules read settings at import time.
from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402, F401  (registers all tables on Base.metadata)
from app.db import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture
def db() -> Iterator[Session]:
    """A fresh, empty in-memory database for each test."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
