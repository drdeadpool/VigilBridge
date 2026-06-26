"""Integration tests for Agreement API endpoints."""

import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db

_USER_ID = str(uuid.uuid4())

_FAKE_SUMMARY = {
    "user_id": _USER_ID,
    "days": 30,
    "total": 12,
    "assessed": 7,
    "confirmed": 5,
    "rejected": 1,
    "needs_review": 1,
    "pending": 5,
    "agreement_rate": 0.7143,
    "disagreement_rate": 0.1429,
    "pending_rate": 0.4167,
    "coverage": 0.5833,
    "mean_confidence": 0.8571,
    "min_confidence": 0.5,
    "max_confidence": 1.0,
    "confidence_distribution": {
        "[0.0, 0.25)": 0,
        "[0.25, 0.5)": 1,
        "[0.5, 0.75)": 2,
        "[0.75, 1.0]": 9,
    },
    "inference_by_version": {"0.1": 12},
}

_FAKE_BY_STATE = {
    "user_id": _USER_ID,
    "days": 30,
    "by_state": [
        {
            "inferred_state": "normal",
            "total": 7,
            "confirmed": 3,
            "rejected": 1,
            "needs_review": 0,
            "pending": 3,
            "agreement_rate": 0.75,
            "disagreement_rate": 0.25,
        },
        {
            "inferred_state": "data_gap",
            "total": 5,
            "confirmed": 2,
            "rejected": 0,
            "needs_review": 1,
            "pending": 2,
            "agreement_rate": 0.6667,
            "disagreement_rate": 0.0,
        },
    ],
}


async def _mock_db() -> AsyncGenerator[AsyncSession, None]:
    yield AsyncMock(spec=AsyncSession)


app.dependency_overrides[get_db] = _mock_db

client = TestClient(app, raise_server_exceptions=False)

READ_HEADERS = {"X-API-Key": "test-read-key"}
INGEST_HEADERS = {"X-API-Key": "test-ingest-key"}


class TestAgreementSummary:
    @patch("app.api.v1.agreement.agreement_service.get_summary", new_callable=AsyncMock)
    def test_returns_all_metric_keys(self, mock_get):
        mock_get.return_value = _FAKE_SUMMARY

        resp = client.get(f"/agreement/{_USER_ID}", headers=READ_HEADERS)
        assert resp.status_code == 200
        body = resp.json()

        for key in (
            "total", "assessed", "confirmed", "rejected", "needs_review", "pending",
            "agreement_rate", "disagreement_rate", "pending_rate", "coverage",
            "mean_confidence", "min_confidence", "max_confidence",
            "confidence_distribution", "inference_by_version",
        ):
            assert key in body, f"missing key: {key}"

    @patch("app.api.v1.agreement.agreement_service.get_summary", new_callable=AsyncMock)
    def test_rejects_ingest_key(self, mock_get):
        mock_get.return_value = _FAKE_SUMMARY
        resp = client.get(f"/agreement/{_USER_ID}", headers=INGEST_HEADERS)
        assert resp.status_code == 401

    @patch("app.api.v1.agreement.agreement_service.get_summary", new_callable=AsyncMock)
    def test_default_days_is_30(self, mock_get):
        mock_get.return_value = _FAKE_SUMMARY
        resp = client.get(f"/agreement/{_USER_ID}", headers=READ_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["days"] == 30

    @patch("app.api.v1.agreement.agreement_service.get_summary", new_callable=AsyncMock)
    def test_custom_days_param(self, mock_get):
        custom = {**_FAKE_SUMMARY, "days": 7}
        mock_get.return_value = custom
        resp = client.get(f"/agreement/{_USER_ID}?days=7", headers=READ_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["days"] == 7

    @patch("app.api.v1.agreement.agreement_service.get_summary", new_callable=AsyncMock)
    def test_confidence_distribution_has_four_buckets(self, mock_get):
        mock_get.return_value = _FAKE_SUMMARY
        resp = client.get(f"/agreement/{_USER_ID}", headers=READ_HEADERS)
        dist = resp.json()["confidence_distribution"]
        assert len(dist) == 4
        for bucket in ("[0.0, 0.25)", "[0.25, 0.5)", "[0.5, 0.75)", "[0.75, 1.0]"):
            assert bucket in dist

    @patch("app.api.v1.agreement.agreement_service.get_summary", new_callable=AsyncMock)
    def test_null_rates_when_no_assessments(self, mock_get):
        zero_summary = {**_FAKE_SUMMARY,
                        "assessed": 0, "confirmed": 0, "rejected": 0,
                        "agreement_rate": None, "disagreement_rate": None,
                        "coverage": None}
        mock_get.return_value = zero_summary
        resp = client.get(f"/agreement/{_USER_ID}", headers=READ_HEADERS)
        body = resp.json()
        assert body["agreement_rate"] is None
        assert body["disagreement_rate"] is None

    @patch("app.api.v1.agreement.agreement_service.get_summary", new_callable=AsyncMock)
    def test_inference_by_version_present(self, mock_get):
        mock_get.return_value = _FAKE_SUMMARY
        resp = client.get(f"/agreement/{_USER_ID}", headers=READ_HEADERS)
        versions = resp.json()["inference_by_version"]
        assert isinstance(versions, dict)
        assert "0.1" in versions


class TestAgreementByState:
    @patch("app.api.v1.agreement.agreement_service.get_by_state", new_callable=AsyncMock)
    def test_returns_by_state_list(self, mock_get):
        mock_get.return_value = _FAKE_BY_STATE
        resp = client.get(f"/agreement/{_USER_ID}/by-state", headers=READ_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "by_state" in body
        assert isinstance(body["by_state"], list)

    @patch("app.api.v1.agreement.agreement_service.get_by_state", new_callable=AsyncMock)
    def test_each_state_entry_has_required_keys(self, mock_get):
        mock_get.return_value = _FAKE_BY_STATE
        resp = client.get(f"/agreement/{_USER_ID}/by-state", headers=READ_HEADERS)
        for entry in resp.json()["by_state"]:
            for key in ("inferred_state", "total", "confirmed", "rejected",
                        "needs_review", "pending", "agreement_rate", "disagreement_rate"):
                assert key in entry, f"missing key: {key}"

    @patch("app.api.v1.agreement.agreement_service.get_by_state", new_callable=AsyncMock)
    def test_rejects_ingest_key(self, mock_get):
        mock_get.return_value = _FAKE_BY_STATE
        resp = client.get(f"/agreement/{_USER_ID}/by-state", headers=INGEST_HEADERS)
        assert resp.status_code == 401

    @patch("app.api.v1.agreement.agreement_service.get_by_state", new_callable=AsyncMock)
    def test_empty_by_state_when_no_records(self, mock_get):
        mock_get.return_value = {"user_id": _USER_ID, "days": 30, "by_state": []}
        resp = client.get(f"/agreement/{_USER_ID}/by-state", headers=READ_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["by_state"] == []

    @patch("app.api.v1.agreement.agreement_service.get_by_state", new_callable=AsyncMock)
    def test_needs_review_state_has_partial_rates(self, mock_get):
        mock_get.return_value = _FAKE_BY_STATE
        resp = client.get(f"/agreement/{_USER_ID}/by-state", headers=READ_HEADERS)
        data_gap = next(e for e in resp.json()["by_state"] if e["inferred_state"] == "data_gap")
        # confirmed=2, rejected=0, needs_review=1 → assessed=3, agreement_rate = 2/3 ≈ 0.6667
        assert data_gap["agreement_rate"] is not None
        assert abs(data_gap["agreement_rate"] - 0.6667) < 0.001


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
