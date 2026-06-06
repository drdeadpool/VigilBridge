import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def compute_baseline(
    db: AsyncSession,
    user_id: uuid.UUID,
    metric_type: str,
    period_days: int,
) -> None:
    """
    Compute and upsert a personal baseline for one metric over a rolling window.

    Algorithm (not yet implemented):
    1. Query valid daily averages for user+metric over the past period_days days.
    2. Require n >= 3 distinct days before writing a row.
    3. Compute mean and std of daily averages (not per-raw-observation).
    4. Upsert into baselines ON CONFLICT (user_id, metric_type, period_days).

    Called after each successful /ingest that inserts new observations.
    Deferred until >=7 valid device observations exist (~2026-06-13).
    """
    raise NotImplementedError("Baseline computation deferred to Phase 2 implementation gate (~2026-06-13)")
