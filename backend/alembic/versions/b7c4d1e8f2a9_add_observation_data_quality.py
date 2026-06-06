"""add observation data quality metadata

Revision ID: b7c4d1e8f2a9
Revises: a3f92c1d4e87
Create Date: 2026-06-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c4d1e8f2a9"
down_revision: Union[str, Sequence[str], None] = "a3f92c1d4e87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column(
            "data_quality_status",
            sa.String(length=32),
            server_default="valid",
            nullable=False,
        ),
    )
    op.add_column(
        "observations",
        sa.Column("quality_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "observations",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_observations_data_quality_status",
        "observations",
        ["data_quality_status"],
    )
    op.create_index(
        "ix_observations_analytics_scope",
        "observations",
        ["user_id", "metric_type", "data_quality_status", "timestamp"],
    )

    op.execute(
        """
        UPDATE observations
        SET data_quality_status = 'probe',
            quality_reason = 'fixture timestamp predates live collection',
            reviewed_at = now()
        WHERE timestamp < TIMESTAMPTZ '2026-01-01 00:00:00+00'
        """
    )
    op.execute(
        """
        UPDATE observations
        SET data_quality_status = 'probe',
            quality_reason = 'event timestamp was in the future at ingestion',
            reviewed_at = now()
        WHERE data_quality_status = 'valid'
          AND timestamp > created_at + INTERVAL '5 minutes'
        """
    )
    op.execute(
        """
        UPDATE observations
        SET data_quality_status = 'legacy',
            quality_reason = 'deprecated pre-canonical sleep metric',
            reviewed_at = now()
        WHERE data_quality_status = 'valid'
          AND metric_type IN ('sleep_duration_minutes', 'sleep_midpoint_hour')
        """
    )
    op.execute(
        """
        UPDATE observations
        SET data_quality_status = 'superseded',
            quality_reason = 'pre-INV-001 fragmented sleep value',
            reviewed_at = now()
        WHERE data_quality_status = 'valid'
          AND (
            (
                metric_type = 'sleep_duration_hours'
                AND timestamp = TIMESTAMPTZ '2026-06-05 20:18:00+00'
                AND value = 4.55
            )
            OR (
                metric_type = 'sleep_end_hour'
                AND timestamp = TIMESTAMPTZ '2026-06-06 00:51:00+00'
                AND value = 6.35
            )
          )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_observations_analytics_scope", table_name="observations")
    op.drop_index("ix_observations_data_quality_status", table_name="observations")
    op.drop_column("observations", "reviewed_at")
    op.drop_column("observations", "quality_reason")
    op.drop_column("observations", "data_quality_status")
