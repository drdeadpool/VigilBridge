import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_read_key
from app.database import get_db
from app.models import Observation

PHASE2_METRICS = frozenset({
    "sleep_duration_hours",
    "time_in_bed_hours",
    "sleep_start_hour",
    "sleep_end_hour",
    "steps_today",
})
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
    if metric not in PHASE2_METRICS:
        raise HTTPException(400, f"Unknown metric. Valid: {sorted(PHASE2_METRICS)}")
    if period not in VALID_PERIODS:
        raise HTTPException(400, f"Invalid period. Valid: {sorted(VALID_PERIODS)}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=period)
    result = await db.execute(
        select(
            func.count(func.distinct(func.date_trunc("day", Observation.timestamp)))
        ).where(
            Observation.user_id == user_id,
            Observation.metric_type == metric,
            Observation.data_quality_status == "valid",
            Observation.timestamp > cutoff,
        )
    )
    valid_days: int = result.scalar_one()

    if valid_days < MIN_VALID_DAYS:
        return {
            "status": "insufficient_data",
            "metric": metric,
            "period_days": period,
            "valid_days": valid_days,
            "required": MIN_VALID_DAYS,
        }

    raise HTTPException(501, "Trend computation not yet implemented — accumulate ≥7 valid days first")
