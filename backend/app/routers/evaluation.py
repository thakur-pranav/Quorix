"""Evaluation API (SPEC section 4): the org's latest evaluation run.

Runs are created by `scripts/run_evaluation.py` (LLM-heavy, minutes long), not by a request.
Org-scoped like every other read: another org's runs are invisible.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db import DbSession
from app.models import EvaluationRun
from app.schemas import EvaluationOut
from app.tenant import CurrentTenant

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation/latest", response_model=EvaluationOut)
def latest_evaluation(tenant: CurrentTenant, db: DbSession) -> EvaluationRun:
    run = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.organization_id == tenant.org)
        .order_by(EvaluationRun.ran_at.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No evaluation yet: run scripts/run_evaluation.py.")
    return run
