"""Shared test setup. Runs before any test module imports the app."""

from __future__ import annotations

import os

from tests.tokens import TEST_JWT_SECRET

# Must be set before `app.config` is imported, because `settings = Settings()` runs at import.
os.environ["BACKEND_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["CHROMA_PATH"] = ":memory:"
# Env vars beat backend/.env, so a developer's real LLM key can never be used by the tests.
os.environ["LLM_PROVIDER"] = "none"


# Imports below the env setup on purpose: app modules read settings at import time.
from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import embeddings, models, vector_store  # noqa: E402, F401  (models registers tables)
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


@pytest.fixture(autouse=True)
def clean_vector_store() -> Iterator[None]:
    """Empty the in-memory Chroma collection after each test that touched it."""
    yield
    if vector_store._collection is not None:
        vector_store.reset_for_tests()


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


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """The real app. `with` runs the lifespan (startup and shutdown) like uvicorn does."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
        # Close the test's session before the app's shutdown runs engine.dispose(), which
        # closes the single shared in-memory connection (StaticPool).
        db.close()
