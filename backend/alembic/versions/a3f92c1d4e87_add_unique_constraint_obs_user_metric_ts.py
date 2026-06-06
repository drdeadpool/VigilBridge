"""add unique constraint on observations(user_id, metric_type, timestamp)

Revision ID: a3f92c1d4e87
Revises: 77f7b348bccf
Create Date: 2026-06-06

Prevents duplicate observations for the same user, metric, and event time.
Sleep timing rows (sleep_start_hour etc.) use the actual event timestamp, so
this constraint deduplicates repeated syncs of the same sleep session.
Steps rows use the sync timestamp (changes per sync) so they are unaffected —
multiple steps_today rows per day is correct time-series behaviour.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a3f92c1d4e87"
down_revision: Union[str, Sequence[str], None] = "77f7b348bccf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove existing duplicate rows first (keep the oldest by created_at).
    # This runs as raw SQL so it works even if there are existing duplicates.
    op.execute("""
        DELETE FROM observations
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id, metric_type, timestamp
                           ORDER BY created_at ASC
                       ) AS rn
                FROM observations
            ) ranked
            WHERE rn > 1
        )
    """)

    op.create_unique_constraint(
        "uq_obs_user_metric_ts",
        "observations",
        ["user_id", "metric_type", "timestamp"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_obs_user_metric_ts", "observations", type_="unique")
