import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ValidationRecord(Base):
    __tablename__ = "validation_records"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_validation_records_user_day"),
        Index("ix_validation_records_user_day", "user_id", "day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)

    engine_version: Mapped[str] = mapped_column(String(16), nullable=False)
    constraint_version: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_model_version: Mapped[str] = mapped_column(String(16), nullable=False)

    inferred_state: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    contributing_constraints: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence_provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    operator_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    inferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
