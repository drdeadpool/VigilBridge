"""Endpoint tests for Trend Engine v1. Service layer is patched; these assert
routing, auth, metric/period validation, the insufficient_data gate, and shape."""

import os
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from fastapi.testclient import TestClient

from app.auth import require_read_key
from app.database import get_db
from app.main import app

USER_ID = "00000000-0000-0000-0000-000000000001"


def _db_override():
    async def override():
        yield AsyncMock()
    return override


def _series(n, start_value=7.0, step=0.1):
    d0 = date(2026, 6, 1)
    return [
        {"date": (d0 + timedelta(days=i)).isoformat(), "value": start_value + i * step}
        for i in range(n)
    ]


class TrendsApiTest(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = _db_override()

    def tearDown(self):
        app.dependency_overrides.clear()

    def _auth(self):
        app.dependency_overrides[require_read_key] = lambda: None

    def test_requires_auth(self):
        r = TestClient(app).get(f"/trends/{USER_ID}?metric=steps_today")
        self.assertEqual(401, r.status_code)

    def test_invalid_metric(self):
        self._auth()
        # sleep_start_hour deliberately excluded from Trend scope (baseline-3 only)
        r = TestClient(app).get(f"/trends/{USER_ID}?metric=sleep_start_hour")
        self.assertEqual(400, r.status_code)

    def test_invalid_period(self):
        self._auth()
        r = TestClient(app).get(f"/trends/{USER_ID}?metric=steps_today&period=5")
        self.assertEqual(400, r.status_code)

    def test_insufficient_data(self):
        self._auth()
        with patch("app.api.v1.trends._fetch_daily_series", new=AsyncMock(return_value=_series(3))):
            r = TestClient(app).get(f"/trends/{USER_ID}?metric=sleep_duration_hours&period=7")
        self.assertEqual(200, r.status_code)
        body = r.json()
        self.assertEqual("insufficient_data", body["status"])
        self.assertEqual(3, body["valid_days"])
        self.assertEqual(7, body["required"])

    def test_success_shape(self):
        self._auth()
        with patch("app.api.v1.trends._fetch_daily_series", new=AsyncMock(return_value=_series(7))):
            r = TestClient(app).get(f"/trends/{USER_ID}?metric=sleep_duration_hours&period=7")
        self.assertEqual(200, r.status_code)
        body = r.json()
        self.assertEqual("sleep_duration_hours", body["metric"])
        self.assertEqual(7, body["period_days"])
        self.assertEqual(7, body["valid_days"])
        self.assertEqual(7, len(body["series"]))
        self.assertEqual("improving", body["trend"]["direction"])
        self.assertIn("slope_per_day", body["trend"])


if __name__ == "__main__":
    unittest.main()
