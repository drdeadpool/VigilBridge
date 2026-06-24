"""Trend Engine v1.

Per-metric daily-reduced time series plus a least-squares slope over a rolling
window, for the same three metrics and daily reduction rules as the Baseline
Engine (ADR-004: one value per local day). No scores, no severity — direction only.

Direction maps the raw slope through each metric's direction-of-good:
    sleep_duration_hours  higher is better (+1)
    steps_today           higher is better (+1)
    resting_hr_bpm        lower  is better (-1)  -> a rising RHR reads as deteriorating

slope_per_day is the raw value/day change (sign as measured); the improving/
deteriorating label applies the direction-of-good sign on top of it.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.baseline_service import LOCAL_TZ, METRIC_DAILY_AGG

TREND_METRICS = tuple(METRIC_DAILY_AGG)

# +1: higher value is an improvement; -1: lower value is an improvement.
METRIC_DIRECTION_OF_GOOD = {
    "sleep_duration_hours": 1,
    "steps_today": 1,
    "resting_hr_bpm": -1,
}

# Slope magnitudes at or below this are treated as flat (numerically stable).
_EPSILON = 1e-9


async def _fetch_daily_series(
    db: AsyncSession, user_id, metric: str, period_days: int
) -> list[dict]:
    """Daily-reduced (local-day) series for one metric over the window, ordered by day.

    Reuses the Baseline daily reduction (steps=max, sleep/hr=avg) and IST bucket so
    trend values match baseline values exactly. `agg` is a literal from the map —
    never user input.
    """
    agg = METRIC_DAILY_AGG[metric]
    sql = text(f"""
        SELECT date(timestamp AT TIME ZONE :tz) AS d, {agg}(value) AS v
        FROM observations
        WHERE user_id = :uid
          AND metric_type = :metric
          AND data_quality_status = 'valid'
          AND value IS NOT NULL
          AND timestamp >= now() - make_interval(days => :days)
        GROUP BY 1
        ORDER BY 1
    """)
    rows = (
        await db.execute(
            sql, {"tz": LOCAL_TZ, "uid": user_id, "metric": metric, "days": period_days}
        )
    ).mappings().all()
    return [{"date": r["d"].isoformat(), "value": float(r["v"])} for r in rows]


def _slope(xs: list[int], ys: list[float]) -> float:
    """Ordinary least-squares slope of ys over xs. Returns 0.0 if x has no spread."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def compute_trend(series: list[dict], metric: str) -> dict:
    """Direction + slope for a daily series. Pure — unit testable.

    direction: improving | stable | deteriorating
    stable when n < 2 or |slope| <= epsilon. slope uses calendar-day x (ordinals)
    so gaps in the series are handled correctly.
    """
    n = len(series)
    values = [float(s["value"]) for s in series]
    first = round(values[0], 4) if n >= 1 else None
    last = round(values[-1], 4) if n >= 1 else None

    if n < 2:
        return {
            "direction": "stable",
            "slope_per_day": 0.0,
            "n_days": n,
            "first": first,
            "last": last,
            "delta": 0.0 if n == 1 else None,
        }

    xs = [date.fromisoformat(s["date"]).toordinal() for s in series]
    slope = _slope(xs, values)
    signed = slope * METRIC_DIRECTION_OF_GOOD.get(metric, 1)
    if abs(slope) <= _EPSILON:
        direction = "stable"
    elif signed > 0:
        direction = "improving"
    else:
        direction = "deteriorating"

    return {
        "direction": direction,
        "slope_per_day": round(slope, 4),
        "n_days": n,
        "first": first,
        "last": last,
        "delta": round(values[-1] - values[0], 4),
    }
