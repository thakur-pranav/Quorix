"""Shared test setup. Runs before any test module imports the app."""

from __future__ import annotations

import os
import sys

from tests.tokens import TEST_JWT_SECRET

# Must be set before `app.config` is imported, because `settings = Settings()` runs at import.
os.environ["BACKEND_JWT_SECRET"] = TEST_JWT_SECRET
# SQLite in memory by default; CI also runs the suite against Postgres + pgvector via TEST_DATABASE_URL.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["ENVIRONMENT"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
# Env vars beat backend/.env, so a developer's real LLM key can never be used by the tests.
os.environ["LLM_PROVIDER"] = "none"
os.environ["WARM_MODELS_ON_STARTUP"] = "false"
os.environ["LLM_MIN_INTERVAL_SECONDS"] = "0"  # no pacing in tests; test_llm turns it on explicitly


# Imports below the env setup on purpose: app modules read settings at import time.
from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text as sql_text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import embeddings, models  # noqa: E402, F401  (models registers tables)
from app.db import Base, SessionLocal, engine  # noqa: E402
from tests.fakes import FAKE_DIMENSION, fake_embed  # noqa: E402


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--real-model", action="store_true", help="also run tests that load the real model"
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "real_model: loads the real embedding model (slow, opt-in)")


@pytest.fixture(autouse=True)
def fake_embeddings(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test uses the fake embedder unless marked `real_model`, so no test downloads 90 MB."""
    if request.node.get_closest_marker("real_model"):
        return
    monkeypatch.setattr(embeddings, "embed", fake_embed)
    monkeypatch.setattr(embeddings, "embed_one", lambda text: fake_embed([text])[0])
    monkeypatch.setattr(embeddings, "dimension", lambda: FAKE_DIMENSION)


@pytest.fixture
def db() -> Iterator[Session]:
    """A fresh, empty database for each test (tables created, then dropped)."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """The real app. `with` runs the lifespan (startup and shutdown) like uvicorn does."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
        # Close the test's session before the app's shutdown runs engine.dispose(), which
        # closes the single shared in-memory connection (StaticPool).
        db.close()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """On GitHub Actions, turn each test failure into an annotation (`::error` workflow command).

    Annotations are readable without logging in (public API) and show inline on pull requests,
    so a CI failure can be diagnosed without downloading the logs. No plugin needed.
    """
    if not os.environ.get("GITHUB_ACTIONS") or not report.failed:
        return

    def escape(text: str, *, prop: bool = False) -> str:
        """GitHub's workflow-command escaping; property values also escape ':' and ','."""
        text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return text.replace(":", "%3A").replace(",", "%2C") if prop else text

    path, line, _ = report.location
    message = "\n".join(str(report.longrepr).splitlines()[-8:])[:1500]
    title = escape(report.nodeid, prop=True)
    # The real stdout: pytest may still be capturing output while this hook runs.
    sys.__stdout__.write(f"\n::error file=backend/{path},line={(line or 0) + 1},title={title}::{escape(message)}\n")
