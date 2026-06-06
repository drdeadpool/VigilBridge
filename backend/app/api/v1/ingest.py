import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Device, Observation, User
from app.schemas.ingest import IngestRequest, IngestResponse, ObservationOut
from app.services.extractor import extract_observations

router = APIRouter()


def _require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    body: IngestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(_require_api_key)],
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
        stmt = (
            pg_insert(Observation)
            .values(
                id=obs_id,
                user_id=user.id,
                device_id=device.id,
                metric_type=obs_data["metric_type"],
                value=obs_data.get("value"),
                unit=obs_data.get("unit"),
                timestamp=obs_data["timestamp"],
                source=obs_data.get("source"),
                raw_payload=body.payload,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "metric_type", "timestamp"]
            )
            .returning(Observation.id, Observation.timestamp)
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is not None:
            saved.append({**obs_data, "id": obs_id})

    await db.commit()

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
