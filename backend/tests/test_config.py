from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_missing_secret_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACKEND_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_short_secret_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, backend_jwt_secret="too-short")


def test_valid_secret_loads() -> None:
    s = Settings(_env_file=None, backend_jwt_secret="x" * 32)
    assert s.backend_jwt_secret == "x" * 32


def test_cors_origins_are_split_and_trimmed() -> None:
    s = Settings(
        _env_file=None,
        backend_jwt_secret="x" * 32,
        cors_origins="http://localhost:3000, https://quorix.app ,",
    )
    assert s.cors_origin_list == ["http://localhost:3000", "https://quorix.app"]


def test_production_refuses_sqlite() -> None:
    """A SQLite file in a container is lost on every redeploy: production must use Postgres."""
    with pytest.raises(ValidationError, match="Postgres DATABASE_URL"):
        Settings(_env_file=None, backend_jwt_secret="x" * 32, environment="production", database_url="sqlite:///./data/q.db")
    ok = Settings(
        _env_file=None, backend_jwt_secret="x" * 32, environment="production",
        database_url="postgresql+psycopg://u:p@db:5432/quorix",
    )  # fmt: skip
    assert ok.environment == "production"
