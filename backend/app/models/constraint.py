import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Constraint(Base):
    __tablename__ = "constraints"
    __table_args__ = (
        UniqueConstraint("user_id", "day", "name", name="uq_constraints_user_day_name"),
        Index("ix_constraints_user_day", "user_id", "day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    fires: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
