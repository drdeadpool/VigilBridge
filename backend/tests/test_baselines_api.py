"""Endpoint tests for Baseline Engine v1. Service layer is patched; these assert
routing, auth, period validation, and payload pass-through."""

import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from fastapi.testclient import TestClient

from app.auth import require_read_key
from app.database import get_db
from app.main import app

USER_ID = "00000000-0000-0000-0000-000000000001"

STATUS_PAYLOAD = {
    "user_id": USER_ID,
    "computed_at": "2026-06-22T18:30:00+00:00",
    "valid_days": 13,
    "sleep_duration_hours": {"baseline": 7.05, "today": 6.2, "std": 0.62, "severity": 1},
    "resting_hr_bpm": {"baseline": 56.4, "today": 60, "std": 2.5, "severity": 1},
    "steps_today": {"baseline": 8421, "today": 5100, "std": 2103, "severity": 1},
}


def _db_override():
    async def override():
        yield AsyncMock()
    return override


class BaselinesApiTest(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = _db_override()

    def tearDown(self):
        app.dependency_overrides.clear()

    def _auth(self):
        app.dependency_overrides[require_read_key] = lambda: None

    def test_status_requires_auth(self):
        # No auth override, no key header -> 401.
        r = TestClient(app).get(f"/baselines/{USER_ID}/status")
        self.assertEqual(401, r.status_code)

    def test_status_returns_payload(self):
        self._auth()
        with patch("app.api.v1.baselines.build_status", new=AsyncMock(return_value=STATUS_PAYLOAD)):
            r = TestClient(app).get(f"/baselines/{USER_ID}/status?period=30")
        self.assertEqual(200, r.status_code)
        body = r.json()
        self.assertEqual(13, body["valid_days"])
        self.assertEqual(1, body["sleep_duration_hours"]["severity"])
        self.assertEqual(8421, body["steps_today"]["baseline"])

    def test_status_rejects_invalid_period(self):
        self._auth()
        r = TestClient(app).get(f"/baselines/{USER_ID}/status?period=5")
        self.assertEqual(400, r.status_code)

    def test_recompute_runs_and_returns_status(self):
        self._auth()
        with patch("app.api.v1.baselines.recompute_baselines_for", new=AsyncMock()) as rc, \
             patch("app.api.v1.baselines.build_status", new=AsyncMock(return_value=STATUS_PAYLOAD)):
            r = TestClient(app).post(f"/baselines/{USER_ID}/recompute?period=30")
        self.assertEqual(200, r.status_code)
        rc.assert_awaited_once()
        self.assertEqual(13, r.json()["valid_days"])

    def test_recompute_rejects_invalid_period(self):
        self._auth()
        r = TestClient(app).post(f"/baselines/{USER_ID}/recompute?period=99")
        self.assertEqual(400, r.status_code)


if __name__ == "__main__":
    unittest.main()
