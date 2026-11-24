"""Shared test setup. Runs before any test module imports the app."""

from __future__ import annotations

import os

# Must be set before `app.config` is imported, because `settings = Settings()` runs at import.
TEST_JWT_SECRET = "test-secret-that-is-definitely-longer-than-32-chars"
os.environ["BACKEND_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
