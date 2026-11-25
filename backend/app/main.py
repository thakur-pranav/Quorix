"""FastAPI application: lifespan, CORS, public health check and the protected /api routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app import embeddings, models, vector_store
from app.config import settings
from app.db import Base, DbSession, engine
from app.routers import chat, sources
from app.schemas import HealthOut
from app.tenant import get_tenant


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Startup. Dev/test only: production schema changes go through Alembic (Day 6, SPEC section 3).
    if settings.environment != "production":
        Base.metadata.create_all(engine)
    if settings.warm_models_on_startup:
        # Load MiniLM and open Chroma now, so the first chat question doesn't wait ~20 s.
        embeddings.embed_one("warm-up")
        vector_store.count()
    yield
    # Shutdown: close pooled DB connections cleanly.
    engine.dispose()


app = FastAPI(title="Quorix API", version="0.1.0", lifespan=lifespan)

# Only the Next.js server calls this API, so the browser rule is narrow: one origin, no cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health(db: DbSession) -> HealthOut:
    """Public: the only route that needs no token."""
    indexed = db.scalar(select(func.count()).select_from(models.Chunk)) or 0
    return HealthOut(indexed_chunks=indexed, llm_provider=settings.llm_provider)


# Secure by default: every router added here requires a valid token, even if a route
# forgets to declare `tenant: CurrentTenant`. (FastAPI runs get_tenant once per request.)
protected = APIRouter(prefix="/api", dependencies=[Depends(get_tenant)])
protected.include_router(sources.router)
protected.include_router(chat.router)
app.include_router(protected)
