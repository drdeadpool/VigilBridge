"""Validation Engine v0.1.

Persists every inference with full version traceability. Operators can assess
records after the fact without touching inference logic.

Design rules:
- create_or_update never overwrites operator_assessment, validation_status, or validated_at
  when a record already exists — operator work is preserved across re-inferences.
- inferred_at records when the state engine ran, not when this function ran.
- All version tags come from app.version so a single version bump propagates automatically.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation_record import ValidationRecord
from app.version import CONSTRAINT_VERSION, ENGINE_VERSION, EVIDENCE_MODEL_VERSION

_UPDATABLE_INFERENCE_COLS = (
    "engine_version",
    "constraint_version",
    "evidence_model_version",
    "inferred_state",
    "confidence",
    "contributing_constraints",
    "evidence_provenance",
    "explanation",
    "inferred_at",
)

_VALID_STATUSES = frozenset({"pending", "confirmed", "rejected", "needs_review"})


def _record_to_dict(row) -> dict:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "day": row.day.isoformat(),
        "engine_version": row.engine_version,
        "constraint_version": row.constraint_version,
        "evidence_model_version": row.evidence_model_version,
        "inferred_state": row.inferred_state,
        "confidence": row.confidence,
        "contributing_constraints": row.contributing_constraints,
        "evidence_provenance": row.evidence_provenance,
        "explanation": row.explanation,
        "validation_status": row.validation_status,
        "operator_assessment": row.operator_assessment,
        "notes": row.notes,
        "inferred_at": row.inferred_at.isoformat() if row.inferred_at else None,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def create_or_update(db: AsyncSession, state_result: dict) -> dict:
    """Upsert a validation record for the given state result.

    On conflict (same user_id + day) updates only inference columns — operator
    assessment columns are left untouched so human review is not clobbered.
    """
    user_id = uuid.UUID(state_result["user_id"])
    day = date.fromisoformat(state_result["day"])
    now_utc = datetime.now(timezone.utc)

    values = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "day": day,
        "engine_version": ENGINE_VERSION,
        "constraint_version": CONSTRAINT_VERSION,
        "evidence_model_version": EVIDENCE_MODEL_VERSION,
        "inferred_state": state_result["state"],
        "confidence": state_result["confidence"],
        "contributing_constraints": state_result["contributing_constraints"],
        "evidence_provenance": state_result["evidence_refs"],
        "explanation": state_result["rationale"],
        "validation_status": "pending",
        "inferred_at": now_utc,
    }

    stmt = (
        pg_insert(ValidationRecord)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["user_id", "day"],
            set_={col: values[col] for col in _UPDATABLE_INFERENCE_COLS},
        )
        .returning(ValidationRecord)
    )
    row = (await db.execute(stmt)).scalar_one()
    await db.commit()
    return _record_to_dict(row)


async def get_record(db: AsyncSession, record_id: uuid.UUID) -> dict | None:
    row = await db.get(ValidationRecord, record_id)
    return _record_to_dict(row) if row else None


async def get_history(db: AsyncSession, user_id: uuid.UUID, days: int = 14) -> list[dict]:
    sql = text(
        """
        SELECT id, user_id, day, engine_version, constraint_version, evidence_model_version,
               inferred_state, confidence, contributing_constraints, evidence_provenance,
               explanation, validation_status, operator_assessment, notes,
               inferred_at, validated_at, created_at
        FROM validation_records
        WHERE user_id = :uid
          AND day >= (now() AT TIME ZONE 'Asia/Kolkata')::date - make_interval(days => :days)
        ORDER BY day DESC
        """
    )
    rows = (await db.execute(sql, {"uid": user_id, "days": days})).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "user_id": str(r["user_id"]),
            "day": r["day"].isoformat(),
            "engine_version": r["engine_version"],
            "constraint_version": r["constraint_version"],
            "evidence_model_version": r["evidence_model_version"],
            "inferred_state": r["inferred_state"],
            "confidence": r["confidence"],
            "contributing_constraints": r["contributing_constraints"],
            "evidence_provenance": r["evidence_provenance"],
            "explanation": r["explanation"],
            "validation_status": r["validation_status"],
            "operator_assessment": r["operator_assessment"],
            "notes": r["notes"],
            "inferred_at": r["inferred_at"].isoformat() if r["inferred_at"] else None,
            "validated_at": r["validated_at"].isoformat() if r["validated_at"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def update_operator(
    db: AsyncSession,
    record_id: uuid.UUID,
    validation_status: str | None = None,
    operator_assessment: str | None = None,
    notes: str | None = None,
) -> dict | None:
    row = await db.get(ValidationRecord, record_id)
    if row is None:
        return None

    changed = False
    if validation_status is not None:
        if validation_status not in _VALID_STATUSES:
            raise ValueError(f"validation_status must be one of {sorted(_VALID_STATUSES)}")
        row.validation_status = validation_status
        row.validated_at = datetime.now(timezone.utc)
        changed = True
    if operator_assessment is not None:
        row.operator_assessment = operator_assessment
        changed = True
    if notes is not None:
        row.notes = notes
        changed = True

    if changed:
        await db.commit()
        await db.refresh(row)

    return _record_to_dict(row)
