#!/bin/sh
# Container entry point: bring the schema up to date, then serve.
# `exec` replaces this shell with uvicorn, so uvicorn is PID 1 and gets Docker's stop signal
# (SIGTERM) directly: in-flight requests finish and the lifespan shutdown runs.
set -eu

# Migrations at startup suit one instance. With several replicas, run them once as a release
# step instead (e.g. Render's pre-deploy command), so instances don't race each other.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
