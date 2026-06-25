import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StateEstimate(Base):
    __tablename__ = "state_estimates"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_state_estimates_user_day"),
        Index("ix_state_estimates_user_day", "user_id", "day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    contributing_constraints: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
