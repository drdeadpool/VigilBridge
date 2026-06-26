"""create validation_records table

Revision ID: a9f4e2d1b6c8
Revises: f2b3c8d5a1e9
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a9f4e2d1b6c8"
down_revision = "f2b3c8d5a1e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("engine_version", sa.String(16), nullable=False),
        sa.Column("constraint_version", sa.String(16), nullable=False),
        sa.Column("evidence_model_version", sa.String(16), nullable=False),
        sa.Column("inferred_state", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("contributing_constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("operator_assessment", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("inferred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "day", name="uq_validation_records_user_day"),
    )
    op.create_index(
        "ix_validation_records_user_day",
        "validation_records",
        ["user_id", "day"],
    )


def downgrade() -> None:
    op.drop_index("ix_validation_records_user_day", table_name="validation_records")
    op.drop_table("validation_records")
