"""Human State Estimator v0.1.

Composes Constraint Engine output into a discrete inferred state per local day.

Properties:
    deterministic — given the same constraint set, the same state is returned
    explainable   — contributing constraints + rationale string accompany every state
    evidence-traced — evidence refs link back to baselines and today's daily-reduced values
    no ML, no LLM, no composite numeric score

Priority cascade (first match wins):
    data_gap          : valid_days < 3 OR any in-scope metric missing today
    recovery_deficit  : sleep_short ∧ rhr_elevated
    strain_overshoot  : steps_high ∧ rhr_elevated ∧ ¬sleep_long
    active_recovery   : steps_low ∧ sleep_long
    normal            : otherwise
"""

import uuid
from datetime import date, datetime, timezone
from statistics import mean as _mean

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StateEstimate
from app.services.baseline_service import BASELINE_METRICS, MIN_VALID_DAYS
from app.services.constraint_engine import (
    compute_and_store_constraints,
    confidence_from_valid_days,
    local_today,
)

STATES = ("data_gap", "recovery_deficit", "strain_overshoot", "active_recovery", "normal")


def _by_name(constraints: list[dict]) -> dict[str, dict]:
    return {c["name"]: c for c in constraints}


def _missing_metrics(today_values: dict[str, float | None]) -> list[str]:
    return [m for m in BASELINE_METRICS if today_values.get(m) is None]


def infer_state(
    constraints: list[dict],
    today_values: dict[str, float | None],
    valid_days: int,
) -> dict:
    """Pure state inference. Returns full estimator record minus persistence keys."""
    by_name = _by_name(constraints)
    missing = _missing_metrics(today_values)

    if valid_days < MIN_VALID_DAYS or missing:
        reason_bits = []
        if valid_days < MIN_VALID_DAYS:
            reason_bits.append(f"valid_days={valid_days} < required {MIN_VALID_DAYS}")
        if missing:
            reason_bits.append(f"missing today: {', '.join(missing)}")
        return {
            "state": "data_gap",
            "confidence": 1.0,
            "contributing_constraints": [],
            "rationale": "Insufficient evidence to estimate state — " + "; ".join(reason_bits),
            "missing_metrics": missing,
        }

    fired = {n: c for n, c in by_name.items() if c["fires"]}

    if "sleep_short" in fired and "rhr_elevated" in fired:
        contributing = ["sleep_short", "rhr_elevated"]
        return _compose(
            state="recovery_deficit",
            contributing=contributing,
            by_name=by_name,
            rationale=(
                "Sleep below personal baseline and resting HR elevated — "
                "consistent with under-recovery."
            ),
        )

    if (
        "steps_high" in fired
        and "rhr_elevated" in fired
        and "sleep_long" not in fired
    ):
        contributing = ["steps_high", "rhr_elevated"]
        return _compose(
            state="strain_overshoot",
            contributing=contributing,
            by_name=by_name,
            rationale=(
                "Activity above baseline alongside elevated resting HR without "
                "compensating extra sleep — strain signal."
            ),
        )

    if "steps_low" in fired and "sleep_long" in fired:
        contributing = ["steps_low", "sleep_long"]
        return _compose(
            state="active_recovery",
            contributing=contributing,
            by_name=by_name,
            rationale=(
                "Activity below baseline with extended sleep — "
                "consistent with active recovery day."
            ),
        )

    return {
        "state": "normal",
        "confidence": round(confidence_from_valid_days(valid_days), 4),
        "contributing_constraints": [],
        "rationale": (
            "No constraint group satisfied; daily-reduced metrics within ±1 SD of baseline."
        ),
        "missing_metrics": [],
    }


def _compose(state: str, contributing: list[str], by_name: dict[str, dict], rationale: str) -> dict:
    confs = [by_name[n]["confidence"] for n in contributing]
    return {
        "state": state,
        "confidence": round(float(_mean(confs)) if confs else 0.0, 4),
        "contributing_constraints": contributing,
        "rationale": rationale,
        "missing_metrics": [],
    }


def build_evidence_refs(
    today_values: dict[str, float | None],
    stats: dict[str, tuple[float, float]],
    valid_days: int,
    period_days: int,
) -> dict:
    return {
        "today_values": {m: today_values.get(m) for m in BASELINE_METRICS},
        "baselines_used": [
            {
                "metric": m,
                "mean": stats[m][0] if m in stats else None,
                "std": stats[m][1] if m in stats else None,
                "period_days": period_days,
            }
            for m in BASELINE_METRICS
        ],
        "valid_days": valid_days,
    }


async def compute_and_store_state(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_days: int = 30,
    day: date | None = None,
) -> dict:
    """Evaluate constraints, infer state, persist both. Single recompute pass."""
    target_day = day or local_today()

    ctx = await compute_and_store_constraints(db, user_id, period_days=period_days, day=target_day)
    constraints = ctx["constraints"]
    today_values = ctx["today_values"]
    stats = ctx["stats"]
    valid_days = ctx["valid_days"]

    inferred = infer_state(constraints, today_values, valid_days)
    evidence_refs = build_evidence_refs(today_values, stats, valid_days, period_days)

    stmt = pg_insert(StateEstimate).values(
        id=uuid.uuid4(),
        user_id=user_id,
        day=target_day,
        state=inferred["state"],
        confidence=inferred["confidence"],
        contributing_constraints=inferred["contributing_constraints"],
        evidence_refs=evidence_refs,
        rationale=inferred["rationale"],
    ).on_conflict_do_update(
        index_elements=["user_id", "day"],
        set_={
            "state": inferred["state"],
            "confidence": inferred["confidence"],
            "contributing_constraints": inferred["contributing_constraints"],
            "evidence_refs": evidence_refs,
            "rationale": inferred["rationale"],
            "computed_at": text("now()"),
        },
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "user_id": str(user_id),
        "day": target_day.isoformat(),
        "state": inferred["state"],
        "confidence": inferred["confidence"],
        "contributing_constraints": inferred["contributing_constraints"],
        "rationale": inferred["rationale"],
        "evidence_refs": evidence_refs,
        "constraints": constraints,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_current_state(
    db: AsyncSession, user_id: uuid.UUID, period_days: int = 30
) -> dict:
    """Read-only path: compute state for today without DB writes; for GET endpoints
    we still hit storage upsert so the read returns persisted truth.
    """
    return await compute_and_store_state(db, user_id, period_days=period_days)


async def get_state_history(
    db: AsyncSession, user_id: uuid.UUID, days: int = 14
) -> list[dict]:
    sql = text(
        """
        SELECT day, state, confidence, contributing_constraints, rationale, computed_at
        FROM state_estimates
        WHERE user_id = :uid
          AND day >= (now() AT TIME ZONE 'Asia/Kolkata')::date - make_interval(days => :days)
        ORDER BY day DESC
        """
    )
    rows = (await db.execute(sql, {"uid": user_id, "days": days})).mappings().all()
    return [
        {
            "day": r["day"].isoformat(),
            "state": r["state"],
            "confidence": r["confidence"],
            "contributing_constraints": r["contributing_constraints"],
            "rationale": r["rationale"],
            "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
        }
        for r in rows
    ]
