"""Gate + validation tests for Trend Engine v1.

Updated for the v1 contract: trend scope is the Baseline-3 metrics only
(sleep_duration_hours, steps_today, resting_hr_bpm), the valid-day gate is driven
by the length of the daily-reduced series (IST), and >= 7 valid days now returns a
computed trend (the old 501 placeholder is gone). The sleep_start/end_hour and
time_in_bed_hours metrics are deliberately out of trend scope and rejected with 400.
"""

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

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def _db_override():
    async def override():
        yield AsyncMock()
    return override


def _series(n: int, start_value: float = 7.0, step: float = 0.1) -> list[dict]:
    d0 = date(2026, 6, 1)
    return [
        {"date": (d0 + timedelta(days=i)).isoformat(), "value": start_value + i * step}
        for i in range(n)
    ]


class TrendsGateTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_read_key] = lambda: None
        app.dependency_overrides[get_db] = _db_override()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _url(self, metric: str = "sleep_duration_hours", period: int = 7) -> str:
        return f"/trends/{TEST_USER_ID}?metric={metric}&period={period}"

    def _get(self, valid_days: int, **kw):
        with patch("app.api.v1.trends._fetch_daily_series",
                   new=AsyncMock(return_value=_series(valid_days))):
            return self.client.get(self._url(**kw))

    def test_zero_valid_days_returns_insufficient_data(self) -> None:
        r = self._get(0)
        self.assertEqual(200, r.status_code)
        body = r.json()
        self.assertEqual("insufficient_data", body["status"])
        self.assertEqual(0, body["valid_days"])
        self.assertEqual(7, body["required"])

    def test_six_valid_days_returns_insufficient_data(self) -> None:
        r = self._get(6)
        self.assertEqual(200, r.status_code)
        self.assertEqual("insufficient_data", r.json()["status"])
        self.assertEqual(6, r.json()["valid_days"])

    def test_seven_valid_days_returns_trend(self) -> None:
        r = self._get(7)
        self.assertEqual(200, r.status_code)
        body = r.json()
        self.assertNotIn("status", body)
        self.assertEqual(7, body["valid_days"])
        self.assertIn("trend", body)
        self.assertIn("direction", body["trend"])

    def test_fourteen_day_period_insufficient_data(self) -> None:
        r = self._get(3, period=14)
        self.assertEqual(200, r.status_code)
        self.assertEqual("insufficient_data", r.json()["status"])
        self.assertEqual(14, r.json()["period_days"])

    def test_unknown_metric_rejected(self) -> None:
        r = self.client.get(self._url(metric="heartrate_composite"))
        self.assertEqual(400, r.status_code)

    def test_invalid_period_rejected(self) -> None:
        r = self.client.get(self._url(period=5))
        self.assertEqual(400, r.status_code)

    def test_baseline_three_metrics_accepted(self) -> None:
        for metric in ("sleep_duration_hours", "steps_today", "resting_hr_bpm"):
            with self.subTest(metric=metric):
                with patch("app.api.v1.trends._fetch_daily_series",
                           new=AsyncMock(return_value=_series(0))):
                    r = self.client.get(self._url(metric=metric))
                self.assertEqual(200, r.status_code)

    def test_out_of_scope_metrics_rejected(self) -> None:
        # Deliberately excluded from trend scope (baseline-3 only).
        for metric in ("time_in_bed_hours", "sleep_start_hour", "sleep_end_hour"):
            with self.subTest(metric=metric):
                r = self.client.get(self._url(metric=metric))
                self.assertEqual(400, r.status_code)


if __name__ == "__main__":
    unittest.main()
