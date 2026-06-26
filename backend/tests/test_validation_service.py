"""Unit tests for Validation Engine v0.1 pure logic."""

import os
import types
import unittest
import uuid
from datetime import date, datetime, timezone

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from app.services.validation_service import _VALID_STATUSES, _record_to_dict
from app.version import CONSTRAINT_VERSION, ENGINE_VERSION, EVIDENCE_MODEL_VERSION


def _make_state_result(
    user_id=None,
    day=None,
    state="normal",
    confidence=1.0,
    contributing_constraints=None,
    rationale="No constraint group satisfied.",
    evidence_refs=None,
) -> dict:
    return {
        "user_id": str(user_id or uuid.uuid4()),
        "day": (day or date.today()).isoformat(),
        "state": state,
        "confidence": confidence,
        "contributing_constraints": contributing_constraints or [],
        "rationale": rationale,
        "evidence_refs": evidence_refs or {"today_values": {}, "baselines_used": [], "valid_days": 14},
        "constraints": [],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_validation_row(user_id=None, day=None, state="normal") -> object:
    """Minimal stand-in for a ValidationRecord ORM row."""
    return types.SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        day=day or date.today(),
        engine_version=ENGINE_VERSION,
        constraint_version=CONSTRAINT_VERSION,
        evidence_model_version=EVIDENCE_MODEL_VERSION,
        inferred_state=state,
        confidence=1.0,
        contributing_constraints=[],
        evidence_provenance={},
        explanation="Normal.",
        validation_status="pending",
        operator_assessment=None,
        notes=None,
        inferred_at=datetime.now(timezone.utc),
        validated_at=None,
        created_at=datetime.now(timezone.utc),
    )


class VersionConstantsTest(unittest.TestCase):
    def test_versions_are_strings(self):
        self.assertIsInstance(ENGINE_VERSION, str)
        self.assertIsInstance(CONSTRAINT_VERSION, str)
        self.assertIsInstance(EVIDENCE_MODEL_VERSION, str)

    def test_version_values(self):
        self.assertEqual("0.1", ENGINE_VERSION)
        self.assertEqual("0.1", CONSTRAINT_VERSION)
        self.assertEqual("0.1", EVIDENCE_MODEL_VERSION)


class ValidStatusSetTest(unittest.TestCase):
    def test_contains_required_statuses(self):
        required = {"pending", "confirmed", "rejected", "needs_review"}
        self.assertEqual(required, _VALID_STATUSES)


class RecordToDictTest(unittest.TestCase):
    def test_all_keys_present(self):
        row = _make_validation_row()
        d = _record_to_dict(row)
        expected_keys = {
            "id", "user_id", "day",
            "engine_version", "constraint_version", "evidence_model_version",
            "inferred_state", "confidence", "contributing_constraints",
            "evidence_provenance", "explanation",
            "validation_status", "operator_assessment", "notes",
            "inferred_at", "validated_at", "created_at",
        }
        self.assertEqual(expected_keys, set(d.keys()))

    def test_uuid_fields_are_strings(self):
        row = _make_validation_row()
        d = _record_to_dict(row)
        self.assertIsInstance(d["id"], str)
        self.assertIsInstance(d["user_id"], str)

    def test_day_is_iso_string(self):
        row = _make_validation_row(day=date(2026, 6, 26))
        d = _record_to_dict(row)
        self.assertEqual("2026-06-26", d["day"])

    def test_datetime_fields_are_iso_strings(self):
        row = _make_validation_row()
        d = _record_to_dict(row)
        self.assertIsInstance(d["inferred_at"], str)
        self.assertIsInstance(d["created_at"], str)
        self.assertIsNone(d["validated_at"])

    def test_pending_status_default(self):
        row = _make_validation_row()
        d = _record_to_dict(row)
        self.assertEqual("pending", d["validation_status"])


class StateResultMappingTest(unittest.TestCase):
    def test_state_result_has_required_keys(self):
        sr = _make_state_result()
        for key in ("user_id", "day", "state", "confidence", "contributing_constraints",
                    "rationale", "evidence_refs"):
            self.assertIn(key, sr)

    def test_recovery_deficit_state_result(self):
        sr = _make_state_result(
            state="recovery_deficit",
            confidence=0.8571,
            contributing_constraints=["sleep_short", "rhr_elevated"],
            rationale="Sleep below baseline and RHR elevated.",
        )
        self.assertEqual("recovery_deficit", sr["state"])
        self.assertEqual(["sleep_short", "rhr_elevated"], sr["contributing_constraints"])

    def test_data_gap_state_result(self):
        sr = _make_state_result(state="data_gap", confidence=1.0, contributing_constraints=[])
        self.assertEqual("data_gap", sr["state"])
        self.assertEqual([], sr["contributing_constraints"])


class ValidationStatusVocabularyTest(unittest.TestCase):
    def test_all_statuses_are_strings(self):
        for s in _VALID_STATUSES:
            self.assertIsInstance(s, str)

    def test_status_count(self):
        self.assertEqual(4, len(_VALID_STATUSES))


if __name__ == "__main__":
    unittest.main()
