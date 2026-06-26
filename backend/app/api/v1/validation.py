import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_ingest_key, require_read_key
from app.database import get_db
from app.services import validation_service
from app.services.state_service import compute_and_store_state

logger = logging.getLogger(__name__)
router = APIRouter()


class ValidationTriggerRequest(BaseModel):
    user_id: uuid.UUID
    day: str | None = None


class OperatorUpdateRequest(BaseModel):
    validation_status: str | None = None
    operator_assessment: str | None = None
    notes: str | None = None


@router.post("/validation")
async def trigger_validation(
    body: ValidationTriggerRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_ingest_key)],
) -> dict:
    """Recompute state for user and persist a versioned validation record."""
    from datetime import date

    kwargs: dict = {"db": db, "user_id": body.user_id}
    if body.day:
        kwargs["day"] = date.fromisoformat(body.day)

    state_result = await compute_and_store_state(**kwargs)
    record = await validation_service.create_or_update(db, state_result)
    return record


@router.get("/validation")
async def list_validation(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
    days: int = Query(default=14, ge=1, le=90),
) -> dict:
    records = await validation_service.get_history(db, user_id, days=days)
    return {"user_id": str(user_id), "days": days, "records": records}


@router.get("/validation/{record_id}")
async def get_validation(
    record_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
) -> dict:
    record = await validation_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="validation record not found")
    return record


@router.patch("/validation/{record_id}")
async def update_validation(
    record_id: uuid.UUID,
    body: OperatorUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_read_key)],
) -> dict:
    try:
        record = await validation_service.update_operator(
            db,
            record_id,
            validation_status=body.validation_status,
            operator_assessment=body.operator_assessment,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if record is None:
        raise HTTPException(status_code=404, detail="validation record not found")
    return record
