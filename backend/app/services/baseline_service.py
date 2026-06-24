"""Baseline Engine v1.

Computes personal baselines (mean, std, n, min, max) over a rolling window for
exactly three metrics, plus a status view comparing today's value to baseline.

Scope (v1, frozen): sleep_duration_hours, steps_today, resting_hr_bpm.

Valid Day v1:
    A day is valid only if ALL three metrics have at least one valid observation
    that day. Baselines are computed over valid days only.

Daily reduction (one value per local day, evidence-backed):
    sleep_duration_hours : avg  — one event-anchored row/day; avg is identity
    resting_hr_bpm       : avg  — one anchored row/day; avg collapses any
                                  pre-anchor multi-row days to a single value
    steps_today          : max  — cumulative daily counter. Verified against
                                  production: intraday values rise monotonically
                                  (e.g. 1302->1303->...->3689 on 2026-06-06), so
                                  MAX = end-of-day total. MIN/avg/last undercount.

Readiness gate: n >= 3 valid days, else no baseline is written / returned.

Local day bucket uses Asia/Kolkata (the device user's zone, IST) so resting_hr's
02:00 physiological anchor and steps' cumulative day align to one calendar day.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Baseline

LOCAL_TZ = "Asia/Kolkata"
MIN_VALID_DAYS = 3
PERIODS = (7, 14, 30)

# Per-metric daily reduction SQL aggregate. Values are literal — never user input.
METRIC_DAILY_AGG = {
    "sleep_duration_hours": "avg",
    "resting_hr_bpm": "avg",
    "steps_today": "max",
}
BASELINE_METRICS = tuple(METRIC_DAILY_AGG)

# Rounding precision per metric for the status payload.
_METRIC_ROUND = {
    "sleep_duration_hours": 2,
    "resting_hr_bpm": 2,
    "steps_today": 0,
}


def severity(today: float | None, mean: float, std: float) -> int:
    """Severity v1: standard deviations from baseline mean.

    0 Normal (<1 SD), 1 Mild (1-2 SD), 2 Moderate (2-3 SD), 3 Severe (>3 SD).
    std <= 0 (no spread) or missing today -> 0.
    """
    if today is None or std is None or std <= 0:
        return 0
    z = abs(today - mean) / std
    if z < 1:
        return 0
    if z < 2:
        return 1
    if z < 3:
        return 2
    return 3


def _round(metric: str, value: float | None) -> float | None:
    if value is None:
        return None
    digits = _METRIC_ROUND.get(metric, 2)
    r = round(float(value), digits)
    return int(r) if digits == 0 else r


def assemble_status(
    user_id: str,
    computed_at: str,
    valid_days: int,
    stats: dict[str, tuple[float, float]],
    today: dict[str, float | None],
) -> dict:
    """Build the status payload from precomputed stats. Pure — unit testable."""
    payload: dict = {
        "user_id": str(user_id),
        "computed_at": computed_at,
        "valid_days": valid_days,
    }
    for metric in BASELINE_METRICS:
        if metric not in stats:
            payload[metric] = None
            continue
        mean, std = stats[metric]
        t = today.get(metric)
        payload[metric] = {
            "baseline": _round(metric, mean),
            "today": _round(metric, t),
            "std": _round(metric, std),
            "severity": severity(t, mean, std),
        }
    return payload


async def _fetch_daily_stats(db: AsyncSession, user_id: uuid.UUID, period_days: int):
    """Valid-day baseline stats for all three metrics in one query."""
    sql = text(f"""
        WITH daily AS (
            SELECT date(timestamp AT TIME ZONE :tz) AS d,
                   max(value) FILTER (WHERE metric_type = 'steps_today')          AS steps,
                   avg(value) FILTER (WHERE metric_type = 'sleep_duration_hours') AS sleep,
                   avg(value) FILTER (WHERE metric_type = 'resting_hr_bpm')       AS rhr
            FROM observations
            WHERE user_id = :uid
              AND data_quality_status = 'valid'
              AND value IS NOT NULL
              AND metric_type IN ('steps_today', 'sleep_duration_hours', 'resting_hr_bpm')
              AND timestamp >= now() - make_interval(days => :days)
            GROUP BY 1
        ),
        valid AS (
            SELECT * FROM daily
            WHERE steps IS NOT NULL AND sleep IS NOT NULL AND rhr IS NOT NULL
        )
        SELECT count(*)                                  AS valid_days,
               avg(sleep)  AS sleep_mean, coalesce(stddev_samp(sleep), 0) AS sleep_std,
               min(sleep)  AS sleep_min,  max(sleep)     AS sleep_max,
               avg(steps)  AS steps_mean, coalesce(stddev_samp(steps), 0) AS steps_std,
               min(steps)  AS steps_min,  max(steps)     AS steps_max,
               avg(rhr)    AS rhr_mean,   coalesce(stddev_samp(rhr), 0)   AS rhr_std,
               min(rhr)    AS rhr_min,    max(rhr)       AS rhr_max
        FROM valid
    """)
    row = (await db.execute(sql, {"tz": LOCAL_TZ, "uid": user_id, "days": period_days})).mappings().one()
    return row


async def _fetch_today_values(db: AsyncSession, user_id: uuid.UUID, period_days: int) -> dict:
    """Most recent daily-reduced value per metric (today), within the window."""
    today: dict[str, float | None] = {}
    for metric, agg in METRIC_DAILY_AGG.items():
        sql = text(f"""
            SELECT {agg}(value) AS v
            FROM observations
            WHERE user_id = :uid
              AND metric_type = :metric
              AND data_quality_status = 'valid'
              AND value IS NOT NULL
              AND timestamp >= now() - make_interval(days => :days)
              AND date(timestamp AT TIME ZONE :tz) = (
                  SELECT max(date(timestamp AT TIME ZONE :tz))
                  FROM observations
                  WHERE user_id = :uid AND metric_type = :metric
                    AND data_quality_status = 'valid' AND value IS NOT NULL
                    AND timestamp >= now() - make_interval(days => :days)
              )
        """)
        v = (await db.execute(
            sql, {"tz": LOCAL_TZ, "uid": user_id, "metric": metric, "days": period_days}
        )).scalar_one_or_none()
        today[metric] = float(v) if v is not None else None
    return today


def _stats_from_row(row) -> dict[str, tuple[float, float]]:
    """Extract per-metric (mean, std) from a daily-stats row, skipping nulls."""
    mapping = {
        "sleep_duration_hours": ("sleep_mean", "sleep_std"),
        "resting_hr_bpm": ("rhr_mean", "rhr_std"),
        "steps_today": ("steps_mean", "steps_std"),
    }
    out: dict[str, tuple[float, float]] = {}
    for metric, (mk, sk) in mapping.items():
        if row[mk] is not None:
            out[metric] = (float(row[mk]), float(row[sk]))
    return out


async def compute_and_store_baselines(
    db: AsyncSession, user_id: uuid.UUID, period_days: int
) -> dict | None:
    """Compute valid-day baselines for one period and upsert all three rows.

    Idempotent: ON CONFLICT (user_id, metric_type, period_days) DO UPDATE.
    Returns the stats row, or None if below the n >= 3 valid-day gate.
    """
    if period_days not in PERIODS:
        return None
    row = await _fetch_daily_stats(db, user_id, period_days)
    valid_days = int(row["valid_days"])
    if valid_days < MIN_VALID_DAYS:
        return None

    cols = {
        "sleep_duration_hours": ("sleep_mean", "sleep_std", "sleep_min", "sleep_max"),
        "resting_hr_bpm": ("rhr_mean", "rhr_std", "rhr_min", "rhr_max"),
        "steps_today": ("steps_mean", "steps_std", "steps_min", "steps_max"),
    }
    for metric, (mk, sk, mnk, mxk) in cols.items():
        if row[mk] is None:
            continue
        stmt = pg_insert(Baseline).values(
            id=uuid.uuid4(),
            user_id=user_id,
            metric_type=metric,
            period_days=period_days,
            n=valid_days,
            mean=float(row[mk]),
            std=float(row[sk]),
            min_val=float(row[mnk]),
            max_val=float(row[mxk]),
        ).on_conflict_do_update(
            index_elements=["user_id", "metric_type", "period_days"],
            set_={
                "n": valid_days,
                "mean": float(row[mk]),
                "std": float(row[sk]),
                "min": float(row[mnk]),
                "max": float(row[mxk]),
                "computed_at": func.now(),
            },
        )
        await db.execute(stmt)
    await db.commit()
    return dict(row)


async def recompute_baselines_for(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Recompute and persist baselines across all rolling windows for one user."""
    for period in PERIODS:
        await compute_and_store_baselines(db, user_id, period)


async def build_status(db: AsyncSession, user_id: uuid.UUID, period_days: int = 30) -> dict:
    """Live status payload: baseline vs today + severity per metric, plus valid_days.

    Computed directly from observations so it is never stale. period_days bounds
    the baseline window (default 30 covers all collected data to date).
    """
    row = await _fetch_daily_stats(db, user_id, period_days)
    valid_days = int(row["valid_days"])
    computed_at = datetime.now(timezone.utc).isoformat()

    if valid_days < MIN_VALID_DAYS:
        return {
            "user_id": str(user_id),
            "computed_at": computed_at,
            "valid_days": valid_days,
            "status": "insufficient_data",
            "required": MIN_VALID_DAYS,
        }

    stats = _stats_from_row(row)
    today = await _fetch_today_values(db, user_id, period_days)
    return assemble_status(user_id, computed_at, valid_days, stats, today)
