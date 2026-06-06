import os
import unittest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from fastapi.testclient import TestClient

from app.auth import require_read_key
from app.database import get_db
from app.main import app

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def _make_db_override(valid_days: int):
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = valid_days
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override():
        yield mock_session

    return override


class TrendsGateTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_read_key] = lambda: None

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _client(self, valid_days: int) -> TestClient:
        app.dependency_overrides[get_db] = _make_db_override(valid_days)
        return TestClient(app)

    def _url(self, metric: str = "sleep_duration_hours", period: int = 7) -> str:
        return f"/trends/{TEST_USER_ID}?metric={metric}&period={period}"

    def test_zero_valid_days_returns_insufficient_data(self) -> None:
        r = self._client(0).get(self._url())
        self.assertEqual(200, r.status_code)
        body = r.json()
        self.assertEqual("insufficient_data", body["status"])
        self.assertEqual(0, body["valid_days"])
        self.assertEqual(7, body["required"])

    def test_six_valid_days_returns_insufficient_data(self) -> None:
        r = self._client(6).get(self._url())
        self.assertEqual(200, r.status_code)
        self.assertEqual("insufficient_data", r.json()["status"])
        self.assertEqual(6, r.json()["valid_days"])

    def test_seven_valid_days_passes_gate(self) -> None:
        r = self._client(7).get(self._url())
        self.assertEqual(501, r.status_code)

    def test_fourteen_day_period_insufficient_data(self) -> None:
        r = self._client(3).get(self._url(period=14))
        self.assertEqual(200, r.status_code)
        self.assertEqual("insufficient_data", r.json()["status"])
        self.assertEqual(14, r.json()["period_days"])

    def test_unknown_metric_rejected(self) -> None:
        r = self._client(0).get(self._url(metric="heartrate_composite"))
        self.assertEqual(400, r.status_code)

    def test_invalid_period_rejected(self) -> None:
        r = self._client(0).get(self._url(period=5))
        self.assertEqual(400, r.status_code)

    def test_all_valid_phase2_metrics_accepted(self) -> None:
        metrics = [
            "sleep_duration_hours",
            "time_in_bed_hours",
            "sleep_start_hour",
            "sleep_end_hour",
            "steps_today",
        ]
        client = self._client(0)
        for metric in metrics:
            with self.subTest(metric=metric):
                r = client.get(self._url(metric=metric))
                self.assertIn(r.status_code, (200, 501))


if __name__ == "__main__":
    unittest.main()
