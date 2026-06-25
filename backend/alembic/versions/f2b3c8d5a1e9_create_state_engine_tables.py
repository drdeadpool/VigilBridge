"""create constraints + state_estimates tables

Revision ID: f2b3c8d5a1e9
Revises: e1a2c4f9d3b7
Create Date: 2026-06-25

Sprint 1 (Human State Engine v0.1): persist per-day constraint evaluations and
the inferred state estimate composed from them. Both tables key by (user_id, day)
in local IST so they align with baseline/trend daily reduction.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2b3c8d5a1e9"
down_revision: Union[str, Sequence[str], None] = "e1a2c4f9d3b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "constraints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("fires", sa.Boolean, nullable=False),
        sa.Column("severity", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("evidence", postgresql.JSONB, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_constraints_user_day", "constraints", ["user_id", "day"])
    op.create_unique_constraint(
        "uq_constraints_user_day_name",
        "constraints",
        ["user_id", "day", "name"],
    )

    op.create_table(
        "state_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("contributing_constraints", postgresql.JSONB, nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_state_estimates_user_day", "state_estimates", ["user_id", "day"])
    op.create_unique_constraint(
        "uq_state_estimates_user_day",
        "state_estimates",
        ["user_id", "day"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_state_estimates_user_day", "state_estimates", type_="unique")
    op.drop_index("ix_state_estimates_user_day", table_name="state_estimates")
    op.drop_table("state_estimates")

    op.drop_constraint("uq_constraints_user_day_name", "constraints", type_="unique")
    op.drop_index("ix_constraints_user_day", table_name="constraints")
    op.drop_table("constraints")
