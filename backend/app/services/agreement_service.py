"""Agreement Engine v0.1.

Pure analytics over validation_records. No inference logic, no writes.

Metrics computed:
    agreement_rate          confirmed / assessed        (None if assessed=0)
    disagreement_rate       rejected  / assessed        (None if assessed=0)
    pending_rate            pending   / total           (None if total=0)
    coverage                assessed  / total           (None if total=0)
    confidence_distribution bucketed histogram (4 bands)
    agreement_by_state      per inferred_state breakdown
    inference_by_version    count per engine_version

assessed = confirmed + rejected + needs_review  (i.e. not pending)
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    days: int = 30,
) -> dict:
    """Aggregate agreement stats for a user over the last N days."""
    agg_sql = text(
        """
        SELECT
            COUNT(*)                                                      AS total,
            COUNT(*) FILTER (WHERE validation_status = 'confirmed')       AS confirmed,
            COUNT(*) FILTER (WHERE validation_status = 'rejected')        AS rejected,
            COUNT(*) FILTER (WHERE validation_status = 'needs_review')    AS needs_review,
            COUNT(*) FILTER (WHERE validation_status = 'pending')         AS pending,
            ROUND(AVG(confidence)::numeric, 4)                            AS mean_confidence,
            MIN(confidence)                                               AS min_confidence,
            MAX(confidence)                                               AS max_confidence,
            COUNT(*) FILTER (WHERE confidence <  0.25)                   AS conf_low,
            COUNT(*) FILTER (WHERE confidence >= 0.25 AND confidence < 0.5) AS conf_mid_low,
            COUNT(*) FILTER (WHERE confidence >= 0.5  AND confidence < 0.75) AS conf_mid_high,
            COUNT(*) FILTER (WHERE confidence >= 0.75)                   AS conf_high
        FROM validation_records
        WHERE user_id = :uid
          AND day >= (now() AT TIME ZONE 'Asia/Kolkata')::date
                     - make_interval(days => :days)
        """
    )
    ver_sql = text(
        """
        SELECT engine_version, COUNT(*) AS count
        FROM validation_records
        WHERE user_id = :uid
          AND day >= (now() AT TIME ZONE 'Asia/Kolkata')::date
                     - make_interval(days => :days)
        GROUP BY engine_version
        ORDER BY engine_version
        """
    )

    params = {"uid": user_id, "days": days}
    row = (await db.execute(agg_sql, params)).mappings().one()
    ver_rows = (await db.execute(ver_sql, params)).mappings().all()

    total = int(row["total"])
    confirmed = int(row["confirmed"])
    rejected = int(row["rejected"])
    needs_review = int(row["needs_review"])
    pending = int(row["pending"])
    assessed = confirmed + rejected + needs_review

    confidence_distribution = {
        "[0.0, 0.25)": int(row["conf_low"]),
        "[0.25, 0.5)": int(row["conf_mid_low"]),
        "[0.5, 0.75)": int(row["conf_mid_high"]),
        "[0.75, 1.0]": int(row["conf_high"]),
    }

    return {
        "user_id": str(user_id),
        "days": days,
        "total": total,
        "assessed": assessed,
        "confirmed": confirmed,
        "rejected": rejected,
        "needs_review": needs_review,
        "pending": pending,
        "agreement_rate": _rate(confirmed, assessed),
        "disagreement_rate": _rate(rejected, assessed),
        "pending_rate": _rate(pending, total),
        "coverage": _rate(assessed, total),
        "mean_confidence": float(row["mean_confidence"]) if row["mean_confidence"] is not None else None,
        "min_confidence": float(row["min_confidence"]) if row["min_confidence"] is not None else None,
        "max_confidence": float(row["max_confidence"]) if row["max_confidence"] is not None else None,
        "confidence_distribution": confidence_distribution,
        "inference_by_version": {r["engine_version"]: int(r["count"]) for r in ver_rows},
    }


async def get_by_state(
    db: AsyncSession,
    user_id: uuid.UUID,
    days: int = 30,
) -> dict:
    """Per-inferred-state agreement breakdown."""
    sql = text(
        """
        SELECT
            inferred_state,
            COUNT(*)                                                   AS total,
            COUNT(*) FILTER (WHERE validation_status = 'confirmed')    AS confirmed,
            COUNT(*) FILTER (WHERE validation_status = 'rejected')     AS rejected,
            COUNT(*) FILTER (WHERE validation_status = 'needs_review') AS needs_review,
            COUNT(*) FILTER (WHERE validation_status = 'pending')      AS pending
        FROM validation_records
        WHERE user_id = :uid
          AND day >= (now() AT TIME ZONE 'Asia/Kolkata')::date
                     - make_interval(days => :days)
        GROUP BY inferred_state
        ORDER BY total DESC
        """
    )
    rows = (await db.execute(sql, {"uid": user_id, "days": days})).mappings().all()

    states = []
    for r in rows:
        total = int(r["total"])
        confirmed = int(r["confirmed"])
        rejected = int(r["rejected"])
        needs_review = int(r["needs_review"])
        pending = int(r["pending"])
        assessed = confirmed + rejected + needs_review
        states.append(
            {
                "inferred_state": r["inferred_state"],
                "total": total,
                "confirmed": confirmed,
                "rejected": rejected,
                "needs_review": needs_review,
                "pending": pending,
                "agreement_rate": _rate(confirmed, assessed),
                "disagreement_rate": _rate(rejected, assessed),
            }
        )

    return {"user_id": str(user_id), "days": days, "by_state": states}
