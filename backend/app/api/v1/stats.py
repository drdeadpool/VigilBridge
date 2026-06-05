from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Observation

router = APIRouter()


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
