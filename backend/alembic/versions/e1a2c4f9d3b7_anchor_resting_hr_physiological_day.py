"""anchor existing resting_hr_bpm rows to 02:00 local physiological day

Revision ID: e1a2c4f9d3b7
Revises: d9f3a7b2c5e1
Create Date: 2026-06-22

Collapses historical resting_hr_bpm observations (one row per sync, sync-time
timestamp) into one row per physiological day, anchored at 02:00 local time,
value = MIN(value) per day. Matches the new _extract_vigil_snapshot anchoring
so the unique key (user_id, metric_type, timestamp) holds one stable daily row.

Physiological day rule mirrors HealthRepository.readRestingHR / BUG-006:
  local capture hour >= 6  -> physiological day = that local date
  local capture hour <  6  -> physiological day = previous local date

Timezone is read from raw_payload->>'timezone', falling back to Asia/Kolkata
(the only real device user to date, IST).

DESTRUCTIVE: original sync-time rows are deleted. Take a Render Postgres backup
before running. downgrade() cannot resurrect deleted rows — restore from backup.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e1a2c4f9d3b7"
down_revision: Union[str, Sequence[str], None] = "d9f3a7b2c5e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # gen_random_uuid() is core on PG13+; ensure pgcrypto for older servers.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Step 1 — upsert one anchored row per (user, physiological day), tagged
    # 'anchor_v1_tmp' so step 2 can safely tell new rows from old ones. If an
    # anchored row already exists (new code deployed before this migration), the
    # ON CONFLICT branch tags and corrects it so it survives the delete.
    op.execute("""
        WITH tz_rows AS (
            SELECT o.id, o.user_id, o.device_id, o.value, o.source, o.raw_payload,
                   COALESCE(o.raw_payload->>'timezone', 'Asia/Kolkata') AS tz,
                   (o.timestamp AT TIME ZONE COALESCE(o.raw_payload->>'timezone', 'Asia/Kolkata')) AS local_ts
            FROM observations o
            WHERE o.metric_type = 'resting_hr_bpm'
              AND o.value IS NOT NULL
        ),
        phys AS (
            SELECT *,
                   (CASE WHEN EXTRACT(HOUR FROM local_ts) >= 6
                         THEN local_ts::date
                         ELSE local_ts::date - INTERVAL '1 day' END)::date AS phys_day
            FROM tz_rows
        ),
        agg AS (
            SELECT user_id,
                   tz,
                   phys_day,
                   MIN(value) AS min_value,
                   ((phys_day + TIME '02:00') AT TIME ZONE tz) AS anchor_utc,
                   (array_agg(device_id   ORDER BY local_ts DESC))[1] AS device_id,
                   (array_agg(source      ORDER BY local_ts DESC))[1] AS source,
                   (array_agg(raw_payload ORDER BY local_ts DESC))[1] AS raw_payload
            FROM phys
            GROUP BY user_id, tz, phys_day
        )
        INSERT INTO observations
            (id, user_id, device_id, metric_type, value, unit, timestamp,
             source, raw_payload, data_quality_status, quality_reason)
        SELECT gen_random_uuid(), user_id, device_id, 'resting_hr_bpm', min_value, 'bpm',
               anchor_utc, source, raw_payload, 'valid', 'anchor_v1_tmp'
        FROM agg
        ON CONFLICT (user_id, metric_type, timestamp) DO UPDATE
            SET value               = EXCLUDED.value,
                data_quality_status = 'valid',
                quality_reason      = 'anchor_v1_tmp';
    """)

    # Step 2 — delete the original sync-time rows (everything not tagged).
    op.execute("""
        DELETE FROM observations
        WHERE metric_type = 'resting_hr_bpm'
          AND quality_reason IS DISTINCT FROM 'anchor_v1_tmp';
    """)

    # Step 3 — clear the temporary tag.
    op.execute("""
        UPDATE observations
        SET quality_reason = NULL
        WHERE metric_type = 'resting_hr_bpm'
          AND quality_reason = 'anchor_v1_tmp';
    """)


def downgrade() -> None:
    raise NotImplementedError(
        "Irreversible data migration. Original sync-time resting_hr_bpm rows were "
        "deleted. Restore from the Render Postgres backup taken before upgrade."
    )
