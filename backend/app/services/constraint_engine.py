"""Constraint Engine v0.1.

Deterministic rule evaluator. Each rule turns daily-reduced evidence (today vs
baseline) into a single typed signal: (fires, severity, confidence, evidence).

Reuses Baseline daily reduction + severity. No scoring, no ML, no LLM.

Confidence is a function of evidence completeness only — more valid baseline days
means more reliable rule output. confidence = min(1.0, valid_days / FULL_CONFIDENCE_DAYS).

Rules (v0.1, frozen):
    sleep_short      : sleep_duration_hours below baseline by >=1 SD
    sleep_long       : sleep_duration_hours above baseline by >=1 SD
    steps_low        : steps_today below baseline by >=1 SD
    steps_high       : steps_today above baseline by >=1 SD
    rhr_elevated     : resting_hr_bpm above baseline by >=1 SD
    rhr_suppressed   : resting_hr_bpm below baseline by >=1 SD

Sign-tagged so the State Service can compose them without re-parsing magnitudes.
"""

import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Constraint
from app.services.baseline_service import (
    BASELINE_METRICS,
    LOCAL_TZ,
    MIN_VALID_DAYS,
    _fetch_daily_stats,
    _fetch_today_values,
    _stats_from_row,
    severity,
)

FULL_CONFIDENCE_DAYS = 14

# direction = -1 fires below mean (low side); +1 fires above mean (high side).
RULES: tuple[tuple[str, str, int], ...] = (
    ("sleep_short",    "sleep_duration_hours", -1),
    ("sleep_long",     "sleep_duration_hours", +1),
    ("steps_low",      "steps_today",          -1),
    ("steps_high",     "steps_today",          +1),
    ("rhr_elevated",   "resting_hr_bpm",       +1),
    ("rhr_suppressed", "resting_hr_bpm",       -1),
)


def confidence_from_valid_days(valid_days: int) -> float:
    if valid_days <= 0:
        return 0.0
    return min(1.0, valid_days / FULL_CONFIDENCE_DAYS)


def evaluate_rule(
    name: str,
    metric: str,
    direction: int,
    today: float | None,
    mean: float | None,
    std: float | None,
    valid_days: int,
) -> dict:
    """Pure evaluator. Returns a constraint record. Never raises on missing data."""
    confidence = confidence_from_valid_days(valid_days)
    if today is None or mean is None or std is None or std <= 0:
        z = None
        sev = 0
        fires = False
    else:
        z = (today - mean) / std
        sev = severity(today, mean, std)
        fires = bool(sev >= 1 and ((direction < 0 and z <= -1.0) or (direction > 0 and z >= 1.0)))

    return {
        "name": name,
        "fires": fires,
        "severity": int(sev) if fires else 0,
        "confidence": round(confidence, 4),
        "evidence": {
            "metric": metric,
            "direction": direction,
            "today": None if today is None else round(float(today), 4),
            "baseline_mean": None if mean is None else round(float(mean), 4),
            "baseline_std": None if std is None else round(float(std), 4),
            "z": None if z is None else round(z, 4),
            "valid_days": valid_days,
        },
    }


def evaluate_constraints(
    today_values: dict[str, float | None],
    stats: dict[str, tuple[float, float]],
    valid_days: int,
) -> list[dict]:
    """Evaluate all six rules. Pure — unit testable."""
    out: list[dict] = []
    for name, metric, direction in RULES:
        mean_std = stats.get(metric)
        mean, std = (mean_std if mean_std is not None else (None, None))
        out.append(
            evaluate_rule(
                name=name,
                metric=metric,
                direction=direction,
                today=today_values.get(metric),
                mean=mean,
                std=std,
                valid_days=valid_days,
            )
        )
    return out


def local_today(now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(LOCAL_TZ)).date()


async def compute_and_store_constraints(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_days: int = 30,
    day: date | None = None,
) -> dict:
    """Evaluate constraints from observations + baselines, upsert per (user, day, name).

    Returns a dict with the evaluated constraints and the metadata used by the
    State Service so a single recompute pass produces both layers.
    """
    target_day = day or local_today()

    row = await _fetch_daily_stats(db, user_id, period_days)
    valid_days = int(row["valid_days"])
    today_values = await _fetch_today_values(db, user_id, period_days)
    stats = _stats_from_row(row) if valid_days >= MIN_VALID_DAYS else {}

    constraints = evaluate_constraints(today_values, stats, valid_days)

    for c in constraints:
        stmt = pg_insert(Constraint).values(
            id=uuid.uuid4(),
            user_id=user_id,
            day=target_day,
            name=c["name"],
            fires=c["fires"],
            severity=c["severity"],
            confidence=c["confidence"],
            evidence=c["evidence"],
        ).on_conflict_do_update(
            index_elements=["user_id", "day", "name"],
            set_={
                "fires": c["fires"],
                "severity": c["severity"],
                "confidence": c["confidence"],
                "evidence": c["evidence"],
                "computed_at": text("now()"),
            },
        )
        await db.execute(stmt)
    await db.commit()

    return {
        "day": target_day,
        "valid_days": valid_days,
        "today_values": today_values,
        "stats": stats,
        "constraints": constraints,
        "metrics_in_scope": list(BASELINE_METRICS),
    }
