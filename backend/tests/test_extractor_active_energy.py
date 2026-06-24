"""Tests for active_energy extraction in _extract_vigil_snapshot.

active_energy is a cumulative daily kcal metric read via aggregate(ACTIVE_CALORIES_TOTAL).
Like steps it uses the sync timestamp (not anchored) — intraday values rise through the
day; daily total is MAX(value) per day at the analytics layer. today-only scope.
"""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.extractor import extract_observations

IST = ZoneInfo("Asia/Kolkata")


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _snapshot(capture_local: datetime, **fields) -> dict:
    payload = {
        "record_type": "snapshot",
        "payloadVersion": 3,
        "timestampMs": _ms(capture_local),
        "timezone": "Asia/Kolkata",
    }
    payload.update(fields)
    return payload


def _active_rows(payload: dict) -> list[dict]:
    rows = extract_observations(payload, source="health_connect")
    return [r for r in rows if r["metric_type"] == "active_energy"]


class ActiveEnergyExtractTest(unittest.TestCase):
    def test_active_energy_emitted_with_kcal_unit(self) -> None:
        capture = datetime(2026, 6, 24, 14, 0, tzinfo=IST)
        rows = _active_rows(_snapshot(capture, activeEnergyKcal=412.5))
        self.assertEqual(1, len(rows))
        self.assertEqual("kcal", rows[0]["unit"])
        self.assertEqual(412.5, rows[0]["value"])

    def test_value_is_float(self) -> None:
        capture = datetime(2026, 6, 24, 14, 0, tzinfo=IST)
        rows = _active_rows(_snapshot(capture, activeEnergyKcal=300))
        self.assertIsInstance(rows[0]["value"], float)

    def test_uses_sync_timestamp_not_anchored(self) -> None:
        # Unlike resting_hr, active_energy keeps the sync timestamp.
        capture = datetime(2026, 6, 24, 14, 0, tzinfo=IST)
        rows = _active_rows(_snapshot(capture, activeEnergyKcal=412.5))
        self.assertEqual(_ms(capture), int(rows[0]["timestamp"].timestamp() * 1000))

    def test_snake_case_key_accepted(self) -> None:
        capture = datetime(2026, 6, 24, 14, 0, tzinfo=IST)
        rows = _active_rows(_snapshot(capture, active_energy_kcal=250.0))
        self.assertEqual(250.0, rows[0]["value"])

    def test_absent_emits_no_row(self) -> None:
        capture = datetime(2026, 6, 24, 14, 0, tzinfo=IST)
        self.assertEqual([], _active_rows(_snapshot(capture)))


if __name__ == "__main__":
    unittest.main()
