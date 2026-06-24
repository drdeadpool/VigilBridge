import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_read_key
from app.database import get_db
from app.services.trend_service import (
    TREND_METRICS,
    _fetch_daily_series,
    compute_trend,
)

VALID_PERIODS = frozenset({7, 14, 30})
MIN_VALID_DAYS = 7

router = APIRouter()


@router.get("/trends/{user_id}")
async def trends(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    metric: str = Query(..., description="Metric type to trend"),
    period: int = Query(default=7, description="Rolling window in days (7, 14, or 30)"),
) -> dict:
    if metric not in TREND_METRICS:
        raise HTTPException(400, f"Unknown metric. Valid: {sorted(TREND_METRICS)}")
    if period not in VALID_PERIODS:
        raise HTTPException(400, f"Invalid period. Valid: {sorted(VALID_PERIODS)}")

    series = await _fetch_daily_series(db, user_id, metric, period)
    valid_days = len(series)

    if valid_days < MIN_VALID_DAYS:
        return {
            "status": "insufficient_data",
            "metric": metric,
            "period_days": period,
            "valid_days": valid_days,
            "required": MIN_VALID_DAYS,
        }

    return {
        "metric": metric,
        "period_days": period,
        "valid_days": valid_days,
        "series": series,
        "trend": compute_trend(series, metric),
    }
