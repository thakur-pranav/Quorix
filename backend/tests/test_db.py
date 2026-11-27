from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Chunk


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


def test_foreign_keys_are_enforced(db: Session) -> None:
    """A chunk pointing at a source that doesn't exist must be rejected, on SQLite and Postgres.

    Tests the behaviour, not a setting: SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON`
    is set per connection (app/db.py does it); Postgres always enforces them, and has no PRAGMA.
    """
    db.add(Chunk(id="chk_orphan0001", organization_id="org_a", source_id="src_does_not_exist", text="x"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
