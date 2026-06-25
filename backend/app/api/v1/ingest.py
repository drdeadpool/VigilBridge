import logging
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_ingest_key
from app.database import get_db
from app.models import Device, Observation, User
from app.schemas.ingest import IngestRequest, IngestResponse, ObservationOut
from app.services.baseline_service import BASELINE_METRICS, recompute_baselines_for
from app.services.extractor import extract_observations
from app.services.state_service import compute_and_store_state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    body: IngestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_ingest_key)],
) -> IngestResponse:
    # Upsert user
    result = await db.execute(select(User).where(User.external_id == body.user_external_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(external_id=body.user_external_id)
        db.add(user)
        await db.flush()

    # Upsert device
    result = await db.execute(
        select(Device).where(
            Device.user_id == user.id,
            Device.device_identifier == body.device_identifier,
        )
    )
    device = result.scalar_one_or_none()
    if device is None:
        device = Device(
            user_id=user.id,
            device_identifier=body.device_identifier,
            device_model=body.device_model,
            platform=body.platform,
            source_app=body.source_app,
        )
        db.add(device)
        await db.flush()

    # Extract observations from payload
    extracted = extract_observations(body.payload, source=body.source_app or "health_connect")

    # Insert with ON CONFLICT DO NOTHING — unique key: (user_id, metric_type, timestamp).
    # Sleep timing rows use event-based timestamps (stable per session) so duplicates are
    # silently dropped. Steps rows use sync-based timestamps so each sync creates a new row.
    saved: list[dict] = []
    for obs_data in extracted:
        obs_id = uuid.uuid4()
        insert_stmt = pg_insert(Observation).values(
            id=obs_id,
            user_id=user.id,
            device_id=device.id,
            metric_type=obs_data["metric_type"],
            value=obs_data.get("value"),
            unit=obs_data.get("unit"),
            timestamp=obs_data["timestamp"],
            source=obs_data.get("source"),
            raw_payload=body.payload,
            data_quality_status="valid",
        )
        excluded = insert_stmt.excluded
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["user_id", "metric_type", "timestamp"],
            set_={
                "device_id": excluded.device_id,
                "value": excluded.value,
                "unit": excluded.unit,
                "source": excluded.source,
                "raw_payload": excluded.raw_payload,
                "data_quality_status": "valid",
                "quality_reason": None,
                "reviewed_at": None,
            },
            where=or_(
                Observation.value.is_distinct_from(excluded.value),
                Observation.unit.is_distinct_from(excluded.unit),
                Observation.source.is_distinct_from(excluded.source),
            ),
        ).returning(Observation.id, Observation.timestamp)
        row = (await db.execute(stmt)).one_or_none()
        if row is not None:
            saved.append({**obs_data, "id": row.id})

    await db.commit()

    # Refresh baselines when in-scope metrics were ingested. Never fail ingest on
    # a baseline error — ingestion reliability takes precedence.
    if {s["metric_type"] for s in saved} & set(BASELINE_METRICS):
        try:
            await recompute_baselines_for(db, user.id)
        except Exception:
            logger.exception("baseline recompute failed for user %s", user.id)
        try:
            await compute_and_store_state(db, user.id)
        except Exception:
            logger.exception("state recompute failed for user %s", user.id)

    return IngestResponse(
        accepted=len(saved),
        observations=[
            ObservationOut(
                id=str(s["id"]),
                metric_type=s["metric_type"],
                value=float(s["value"]) if s.get("value") is not None else None,
                unit=s.get("unit"),
                timestamp=s["timestamp"] if isinstance(s["timestamp"], datetime) else s["timestamp"],
                source=s.get("source"),
            )
            for s in saved
        ],
    )
