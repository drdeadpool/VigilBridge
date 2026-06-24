import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_read_key
from app.database import get_db
from app.models import Baseline
from app.schemas.baseline import BaselineListOut, BaselineOut
from app.services.baseline_service import (
    PERIODS,
    build_status,
    recompute_baselines_for,
)

router = APIRouter()


@router.get("/baselines/{user_id}", response_model=BaselineListOut)
async def list_baselines(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    metric: str | None = Query(default=None),
    period: int | None = Query(default=None),
) -> BaselineListOut:
    query = select(Baseline).where(Baseline.user_id == user_id)
    if metric is not None:
        query = query.where(Baseline.metric_type == metric)
    if period is not None:
        query = query.where(Baseline.period_days == period)
    rows = (await db.execute(query)).scalars().all()
    return BaselineListOut(baselines=[BaselineOut.model_validate(r) for r in rows])


@router.get("/baselines/{user_id}/status")
async def baseline_status(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    period: int = Query(default=30),
) -> dict:
    if period not in PERIODS:
        raise HTTPException(400, f"Invalid period. Valid: {sorted(PERIODS)}")
    return await build_status(db, user_id, period)


@router.post("/baselines/{user_id}/recompute")
async def recompute(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    period: int = Query(default=30),
) -> dict:
    if period not in PERIODS:
        raise HTTPException(400, f"Invalid period. Valid: {sorted(PERIODS)}")
    await recompute_baselines_for(db, user_id)
    return await build_status(db, user_id, period)
