import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Observation(Base):
    """
    FHIR-mappable health observation.

    Maps to FHIR Observation resource:
      metric_type  → code.coding[0].code
      unit         → valueQuantity.unit
      value        → valueQuantity.value
      timestamp    → effectiveDateTime
      source       → device.display
      raw_payload  → extension (preserve original HC payload)
    """

    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True, index=True
    )

    # FHIR Observation.code — the type of measurement
    metric_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # FHIR Observation.valueQuantity
    value: Mapped[float | None] = mapped_column(Numeric(precision=12, scale=4))
    unit: Mapped[str | None] = mapped_column(String(64))

    # FHIR Observation.effectiveDateTime — when the measurement was taken
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Originating app/system (e.g. "samsung_health", "health_connect")
    source: Mapped[str | None] = mapped_column(String(128))

    # Full original payload stored for future reprocessing
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="observations")
    device: Mapped["Device | None"] = relationship("Device", back_populates="observations")
