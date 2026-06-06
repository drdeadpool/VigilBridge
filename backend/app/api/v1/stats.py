from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_read_key
from app.database import get_db
from app.models import Observation
from app.services.observation_query import observation_query

router = APIRouter()


@router.get("/observations/recent")
async def observations_recent(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    limit: int = Query(default=20, ge=1, le=100),
    metric_type: str | None = Query(default=None),
    include_invalid: bool = Query(default=False),
) -> list[dict]:
    q = (
        observation_query(include_invalid=include_invalid)
        .order_by(Observation.timestamp.desc())
        .limit(limit)
    )
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
            "data_quality_status": r.data_quality_status,
            "quality_reason": r.quality_reason,
        }
        for r in rows
    ]


@router.get("/stats")
async def stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    include_invalid: bool = Query(default=False),
) -> dict:
    scoped = observation_query(include_invalid=include_invalid).subquery()
    total_result = await db.execute(select(func.count()).select_from(scoped))
    total = total_result.scalar_one()

    types_result = await db.execute(
        select(scoped.c.metric_type, func.count().label("count"))
        .group_by(scoped.c.metric_type)
        .order_by(func.count().desc())
    )
    observation_types = {row.metric_type: row.count for row in types_result}

    latest_result = await db.execute(select(func.max(scoped.c.timestamp)))
    latest_ts = latest_result.scalar_one()

    quality_result = await db.execute(
        select(Observation.data_quality_status, func.count().label("count"))
        .group_by(Observation.data_quality_status)
        .order_by(Observation.data_quality_status)
    )

    return {
        "total_observations": total,
        "observation_types": observation_types,
        "latest_timestamp": latest_ts.isoformat() if latest_ts else None,
        "include_invalid": include_invalid,
        "quality_counts": {
            row.data_quality_status: row.count for row in quality_result
        },
    }
