"""Sources API (SPEC section 4). Day 1: list only. Create, upload, reindex and delete come on Day 2."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.db import DbSession
from app.models import Source
from app.schemas import SourceOut
from app.tenant import CurrentTenant

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(tenant: CurrentTenant, db: DbSession) -> list[Source]:
    """The caller's sources, newest first. Other orgs' sources are never visible."""
    stmt = (
        select(Source)
        .where(Source.organization_id == tenant.org)
        .order_by(Source.created_at.desc(), Source.id.desc())
    )
    return list(db.scalars(stmt))
