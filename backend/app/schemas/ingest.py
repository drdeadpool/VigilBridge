from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """
    Accepts arbitrary Health Connect webhook JSON.
    device_id and user_id are passed as headers or envelope fields.
    All raw payload is preserved.
    """

    user_external_id: str = Field(..., description="Caller-provided user identifier (e.g. device serial, account ID)")
    device_identifier: str = Field(..., description="Device hardware ID or model string")
    device_model: str | None = None
    platform: str | None = "android"
    source_app: str | None = "health_connect"

    # The raw HC webhook payload — stored as-is for future reprocessing
    payload: dict[str, Any] = Field(..., description="Raw Health Connect webhook JSON")


class ObservationOut(BaseModel):
    id: str
    metric_type: str
    value: float | None
    unit: str | None
    timestamp: datetime
    source: str | None

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    accepted: int
    observations: list[ObservationOut]
