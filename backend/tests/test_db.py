from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db


def test_get_db_yields_a_working_session_and_closes_it() -> None:
    gen = get_db()
    db = next(gen)
    assert isinstance(db, Session)
    assert db.execute(text("SELECT 1")).scalar_one() == 1

    with patch.object(db, "close", wraps=db.close) as close_spy:
        next(gen, None)  # resume the generator: the `finally` block runs
    close_spy.assert_called_once()


def test_get_db_closes_session_even_if_route_fails() -> None:
    gen = get_db()
    db = next(gen)
    with patch.object(db, "close", wraps=db.close) as close_spy:
        try:
            gen.throw(RuntimeError("route crashed"))  # what FastAPI does when the handler raises
        except RuntimeError:
            pass
    close_spy.assert_called_once()


def test_sqlite_foreign_keys_are_enforced() -> None:
    db = next(get_db())
    assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    db.close()
