"""POST /api/chat (SPEC section 4): one question in, one grounded answer out."""

from __future__ import annotations

from fastapi import APIRouter

from app.db import DbSession
from app.rag import engine
from app.schemas import ChatRequest, ChatResponse
from app.tenant import CurrentTenant

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, tenant: CurrentTenant, db: DbSession) -> ChatResponse:
    """A plain `def`: embedding and the LLM call are blocking, so this runs in the thread pool."""
    return engine.answer(db, tenant.org, body.session_id, body.question)
