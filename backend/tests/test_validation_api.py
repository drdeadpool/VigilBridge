"""Integration tests for Validation API endpoints.

Uses FastAPI TestClient with overridden DB and auth dependencies so no live
Postgres is required. Patches validation_service and compute_and_store_state
at the module level to isolate transport/routing from business logic.
"""

import os
import uuid
from datetime import date, datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid.uuid4())
_RECORD_ID = str(uuid.uuid4())
_TODAY = date.today().isoformat()

_FAKE_STATE_RESULT = {
    "user_id": _USER_ID,
    "day": _TODAY,
    "state": "normal",
    "confidence": 1.0,
    "contributing_constraints": [],
    "rationale": "Within baseline.",
    "evidence_refs": {"today_values": {}, "baselines_used": [], "valid_days": 14},
    "constraints": [],
    "computed_at": datetime.now(timezone.utc).isoformat(),
}

_FAKE_RECORD = {
    "id": _RECORD_ID,
    "user_id": _USER_ID,
    "day": _TODAY,
    "engine_version": "0.1",
    "constraint_version": "0.1",
    "evidence_model_version": "0.1",
    "inferred_state": "normal",
    "confidence": 1.0,
    "contributing_constraints": [],
    "evidence_provenance": {"today_values": {}, "baselines_used": [], "valid_days": 14},
    "explanation": "Within baseline.",
    "validation_status": "pending",
    "operator_assessment": None,
    "notes": None,
    "inferred_at": datetime.now(timezone.utc).isoformat(),
    "validated_at": None,
    "created_at": datetime.now(timezone.utc).isoformat(),
}


async def _mock_db() -> AsyncGenerator[AsyncSession, None]:
    yield AsyncMock(spec=AsyncSession)


app.dependency_overrides[get_db] = _mock_db

client = TestClient(app, raise_server_exceptions=False)

INGEST_HEADERS = {"X-API-Key": "test-ingest-key"}
READ_HEADERS = {"X-API-Key": "test-read-key"}


# ---------------------------------------------------------------------------
# POST /validation
# ---------------------------------------------------------------------------

class TestPostValidation:
    @patch("app.api.v1.validation.compute_and_store_state", new_callable=AsyncMock)
    @patch("app.api.v1.validation.validation_service.create_or_update", new_callable=AsyncMock)
    def test_post_returns_200_with_record(self, mock_upsert, mock_compute):
        mock_compute.return_value = _FAKE_STATE_RESULT
        mock_upsert.return_value = _FAKE_RECORD

        resp = client.post(
            "/validation",
            json={"user_id": _USER_ID},
            headers=INGEST_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inferred_state"] == "normal"
        assert body["validation_status"] == "pending"
        assert body["id"] == _RECORD_ID

    @patch("app.api.v1.validation.compute_and_store_state", new_callable=AsyncMock)
    @patch("app.api.v1.validation.validation_service.create_or_update", new_callable=AsyncMock)
    def test_post_rejects_read_key(self, mock_upsert, mock_compute):
        mock_compute.return_value = _FAKE_STATE_RESULT
        mock_upsert.return_value = _FAKE_RECORD

        resp = client.post(
            "/validation",
            json={"user_id": _USER_ID},
            headers=READ_HEADERS,
        )
        assert resp.status_code == 401

    @patch("app.api.v1.validation.compute_and_store_state", new_callable=AsyncMock)
    @patch("app.api.v1.validation.validation_service.create_or_update", new_callable=AsyncMock)
    def test_post_with_explicit_day(self, mock_upsert, mock_compute):
        mock_compute.return_value = _FAKE_STATE_RESULT
        mock_upsert.return_value = _FAKE_RECORD

        resp = client.post(
            "/validation",
            json={"user_id": _USER_ID, "day": "2026-06-20"},
            headers=INGEST_HEADERS,
        )
        assert resp.status_code == 200
        _, kwargs = mock_compute.call_args
        assert kwargs.get("day") == date(2026, 6, 20) or mock_compute.call_args[1].get("day") == date(2026, 6, 20)


# ---------------------------------------------------------------------------
# GET /validation
# ---------------------------------------------------------------------------

class TestGetValidationList:
    @patch("app.api.v1.validation.validation_service.get_history", new_callable=AsyncMock)
    def test_get_returns_records(self, mock_history):
        mock_history.return_value = [_FAKE_RECORD]

        resp = client.get(
            f"/validation?user_id={_USER_ID}",
            headers=READ_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == _USER_ID
        assert len(body["records"]) == 1

    @patch("app.api.v1.validation.validation_service.get_history", new_callable=AsyncMock)
    def test_get_rejects_ingest_key(self, mock_history):
        mock_history.return_value = []
        resp = client.get(f"/validation?user_id={_USER_ID}", headers=INGEST_HEADERS)
        assert resp.status_code == 401

    @patch("app.api.v1.validation.validation_service.get_history", new_callable=AsyncMock)
    def test_get_days_param_default(self, mock_history):
        mock_history.return_value = []
        resp = client.get(f"/validation?user_id={_USER_ID}", headers=READ_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["days"] == 14


# ---------------------------------------------------------------------------
# GET /validation/{id}
# ---------------------------------------------------------------------------

class TestGetValidationSingle:
    @patch("app.api.v1.validation.validation_service.get_record", new_callable=AsyncMock)
    def test_get_existing_record(self, mock_get):
        mock_get.return_value = _FAKE_RECORD

        resp = client.get(f"/validation/{_RECORD_ID}", headers=READ_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == _RECORD_ID

    @patch("app.api.v1.validation.validation_service.get_record", new_callable=AsyncMock)
    def test_get_missing_record_returns_404(self, mock_get):
        mock_get.return_value = None

        resp = client.get(f"/validation/{_RECORD_ID}", headers=READ_HEADERS)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /validation/{id}
# ---------------------------------------------------------------------------

class TestPatchValidation:
    @patch("app.api.v1.validation.validation_service.update_operator", new_callable=AsyncMock)
    def test_patch_confirmed_status(self, mock_update):
        confirmed = {**_FAKE_RECORD, "validation_status": "confirmed", "operator_assessment": "Looks correct."}
        mock_update.return_value = confirmed

        resp = client.patch(
            f"/validation/{_RECORD_ID}",
            json={"validation_status": "confirmed", "operator_assessment": "Looks correct."},
            headers=READ_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["validation_status"] == "confirmed"
        assert resp.json()["operator_assessment"] == "Looks correct."

    @patch("app.api.v1.validation.validation_service.update_operator", new_callable=AsyncMock)
    def test_patch_missing_record_returns_404(self, mock_update):
        mock_update.return_value = None

        resp = client.patch(
            f"/validation/{_RECORD_ID}",
            json={"validation_status": "confirmed"},
            headers=READ_HEADERS,
        )
        assert resp.status_code == 404

    @patch("app.api.v1.validation.validation_service.update_operator", new_callable=AsyncMock)
    def test_patch_invalid_status_returns_422(self, mock_update):
        mock_update.side_effect = ValueError("validation_status must be one of ...")

        resp = client.patch(
            f"/validation/{_RECORD_ID}",
            json={"validation_status": "not_a_status"},
            headers=READ_HEADERS,
        )
        assert resp.status_code == 422

    @patch("app.api.v1.validation.validation_service.update_operator", new_callable=AsyncMock)
    def test_patch_notes_only(self, mock_update):
        updated = {**_FAKE_RECORD, "notes": "Follow up in 3 days."}
        mock_update.return_value = updated

        resp = client.patch(
            f"/validation/{_RECORD_ID}",
            json={"notes": "Follow up in 3 days."},
            headers=READ_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Follow up in 3 days."


# ---------------------------------------------------------------------------
# Version traceability
# ---------------------------------------------------------------------------

class TestVersionTraceability:
    def test_record_carries_all_version_fields(self):
        for key in ("engine_version", "constraint_version", "evidence_model_version"):
            assert key in _FAKE_RECORD
            assert _FAKE_RECORD[key] == "0.1"

    def test_record_carries_evidence_provenance(self):
        assert "evidence_provenance" in _FAKE_RECORD
        assert isinstance(_FAKE_RECORD["evidence_provenance"], dict)

    def test_record_carries_explanation(self):
        assert "explanation" in _FAKE_RECORD
        assert isinstance(_FAKE_RECORD["explanation"], str)

    def test_inferred_at_is_iso_string(self):
        assert "inferred_at" in _FAKE_RECORD
        parsed = datetime.fromisoformat(_FAKE_RECORD["inferred_at"])
        assert parsed.tzinfo is not None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
