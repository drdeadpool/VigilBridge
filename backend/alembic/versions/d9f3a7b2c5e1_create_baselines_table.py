"""create baselines table

Revision ID: d9f3a7b2c5e1
Revises: b7c4d1e8f2a9
Create Date: 2026-06-06

Phase 2 scaffold: personal per-metric baselines (mean, std, n) over rolling windows.
Computation deferred until >=7 valid device observations exist (~2026-06-13).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d9f3a7b2c5e1"
down_revision: Union[str, Sequence[str], None] = "b7c4d1e8f2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("metric_type", sa.String(64), nullable=False),
        sa.Column("period_days", sa.Integer, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("n", sa.Integer, nullable=False),
        sa.Column("mean", sa.Float, nullable=False),
        sa.Column("std", sa.Float, nullable=False),
        sa.Column("min", sa.Float, nullable=False),
        sa.Column("max", sa.Float, nullable=False),
    )
    op.create_index("ix_baselines_user_id", "baselines", ["user_id"])
    op.create_unique_constraint(
        "uq_baselines_user_metric_period",
        "baselines",
        ["user_id", "metric_type", "period_days"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_baselines_user_metric_period", "baselines", type_="unique")
    op.drop_index("ix_baselines_user_id", table_name="baselines")
    op.drop_table("baselines")
