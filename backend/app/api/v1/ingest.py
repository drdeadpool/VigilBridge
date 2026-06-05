import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
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

    saved: list[Observation] = []
    for obs_data in extracted:
        obs = Observation(
            id=uuid.uuid4(),
            user_id=user.id,
            device_id=device.id,
            metric_type=obs_data["metric_type"],
            value=obs_data.get("value"),
            unit=obs_data.get("unit"),
            timestamp=obs_data["timestamp"],
            source=obs_data.get("source"),
            raw_payload=body.payload,
        )
        db.add(obs)
        saved.append(obs)

    await db.commit()

    return IngestResponse(
        accepted=len(saved),
        observations=[
            ObservationOut(
                id=str(obs.id),
                metric_type=obs.metric_type,
                value=float(obs.value) if obs.value is not None else None,
                unit=obs.unit,
                timestamp=obs.timestamp,
                source=obs.source,
            )
            for obs in saved
        ],
    )
