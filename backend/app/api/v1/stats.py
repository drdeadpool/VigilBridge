from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Observation

router = APIRouter()


@router.get("/observations/recent")
async def observations_recent(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
    metric_type: str | None = Query(default=None),
) -> list[dict]:
    q = select(Observation).order_by(Observation.timestamp.desc()).limit(limit)
    if metric_type:
        q = q.where(Observation.metric_type == metric_type)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "metric_type": r.metric_type,
            "value": float(r.value) if r.value is not None else None,
            "unit": r.unit,
            "timestamp": r.timestamp.isoformat(),
            "source": r.source,
            "timezone": r.raw_payload.get("timezone") if r.raw_payload else None,
        }
        for r in rows
    ]


@router.get("/stats")
async def stats(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    total_result = await db.execute(select(func.count()).select_from(Observation))
    total = total_result.scalar_one()

    types_result = await db.execute(
        select(Observation.metric_type, func.count().label("count"))
        .group_by(Observation.metric_type)
        .order_by(func.count().desc())
    )
    observation_types = {row.metric_type: row.count for row in types_result}

    latest_result = await db.execute(select(func.max(Observation.timestamp)))
    latest_ts = latest_result.scalar_one()

    return {
        "total_observations": total,
        "observation_types": observation_types,
        "latest_timestamp": latest_ts.isoformat() if latest_ts else None,
    }
