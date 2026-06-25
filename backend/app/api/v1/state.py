import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_read_key
from app.database import get_db
from app.services.state_service import (
    compute_and_store_state,
    get_current_state,
    get_state_history,
)

router = APIRouter()


@router.get("/state/{user_id}")
async def current_state(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    period: int = Query(default=30, ge=3, le=90),
) -> dict:
    return await get_current_state(db, user_id, period_days=period)


@router.get("/state/{user_id}/history")
async def state_history(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    days: int = Query(default=14, ge=1, le=90),
) -> dict:
    history = await get_state_history(db, user_id, days=days)
    return {"user_id": str(user_id), "days": days, "history": history}


@router.post("/state/{user_id}/recompute")
async def recompute_state(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    period: int = Query(default=30, ge=3, le=90),
) -> dict:
    return await compute_and_store_state(db, user_id, period_days=period)
