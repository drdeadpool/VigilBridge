import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_read_key
from app.database import get_db
from app.services import agreement_service

router = APIRouter()


@router.get("/agreement/{user_id}")
async def agreement_summary(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Aggregate agreement metrics for a user over the last N days.

    Returns: agreement_rate, disagreement_rate, pending_rate, coverage,
    confidence_distribution, inference_by_version.
    Rates are null when the denominator is zero (no assessments yet).
    """
    return await agreement_service.get_summary(db, user_id, days=days)


@router.get("/agreement/{user_id}/by-state")
async def agreement_by_state(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Per-inferred-state agreement breakdown."""
    return await agreement_service.get_by_state(db, user_id, days=days)
