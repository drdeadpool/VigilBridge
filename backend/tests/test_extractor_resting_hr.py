"""Tests for resting_hr_bpm physiological-day anchoring in _extract_vigil_snapshot.

BUG: resting_hr_bpm was stored at snapshot sync time -> N rows/day, breaking
ADR-004 baselines. Fix anchors every reading to 02:00 local of its physiological
day so repeated syncs upsert into a single stable daily row.
"""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.extractor import extract_observations

IST = ZoneInfo("Asia/Kolkata")  # UTC+5:30, no DST


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _snapshot(capture_local: datetime, tz: str = "Asia/Kolkata", bpm=57) -> dict:
    return {
        "record_type": "snapshot",
        "payloadVersion": 2,
        "timestampMs": _ms(capture_local),
        "timezone": tz,
        "restingHrBpm": bpm,
    }


def _resting_rows(payload: dict) -> list[dict]:
    rows = extract_observations(payload, source="health_connect")
    return [r for r in rows if r["metric_type"] == "resting_hr_bpm"]


class RestingHrAnchorTest(unittest.TestCase):
    def test_daytime_capture_anchors_to_0200_local_same_day(self) -> None:
        # Capture 14:00 IST on 2026-06-20 -> physiological day 2026-06-20.
        capture = datetime(2026, 6, 20, 14, 0, tzinfo=IST)
        rows = _resting_rows(_snapshot(capture))
        self.assertEqual(1, len(rows))
        anchor_local = rows[0]["timestamp"].astimezone(IST)
        self.assertEqual((2026, 6, 20, 2, 0), (
            anchor_local.year, anchor_local.month, anchor_local.day,
            anchor_local.hour, anchor_local.minute,
        ))

    def test_early_morning_capture_anchors_to_previous_day(self) -> None:
        # Capture 03:00 IST (< 06:00) -> window belongs to previous physiological day.
        capture = datetime(2026, 6, 20, 3, 0, tzinfo=IST)
        rows = _resting_rows(_snapshot(capture))
        self.assertEqual(1, len(rows))
        anchor_local = rows[0]["timestamp"].astimezone(IST)
        self.assertEqual((2026, 6, 19, 2, 0), (
            anchor_local.year, anchor_local.month, anchor_local.day,
            anchor_local.hour, anchor_local.minute,
        ))

    def test_six_am_boundary_is_today(self) -> None:
        capture = datetime(2026, 6, 20, 6, 0, tzinfo=IST)
        rows = _resting_rows(_snapshot(capture))
        anchor_local = rows[0]["timestamp"].astimezone(IST)
        self.assertEqual(20, anchor_local.day)

    def test_two_captures_same_day_yield_identical_timestamp(self) -> None:
        # Idempotency: morning + evening sync of the same physiological day collapse
        # to one upsert key.
        morning = _resting_rows(_snapshot(datetime(2026, 6, 20, 8, 0, tzinfo=IST)))
        evening = _resting_rows(_snapshot(datetime(2026, 6, 20, 22, 0, tzinfo=IST)))
        self.assertEqual(morning[0]["timestamp"], evening[0]["timestamp"])

    def test_anchor_utc_is_2030_previous_day_for_ist(self) -> None:
        # 02:00 IST == 20:30 UTC of the previous calendar day.
        capture = datetime(2026, 6, 20, 14, 0, tzinfo=IST)
        ts = _resting_rows(_snapshot(capture))[0]["timestamp"].astimezone(ZoneInfo("UTC"))
        self.assertEqual((2026, 6, 19, 20, 30), (
            ts.year, ts.month, ts.day, ts.hour, ts.minute,
        ))

    def test_utc_timezone_anchors_to_0200_utc(self) -> None:
        capture = datetime(2026, 6, 20, 14, 0, tzinfo=ZoneInfo("UTC"))
        ts = _resting_rows(_snapshot(capture, tz="UTC"))[0]["timestamp"].astimezone(ZoneInfo("UTC"))
        self.assertEqual((2026, 6, 20, 2, 0), (ts.year, ts.month, ts.day, ts.hour, ts.minute))

    def test_invalid_timezone_falls_back_to_utc(self) -> None:
        capture = datetime(2026, 6, 20, 14, 0, tzinfo=ZoneInfo("UTC"))
        payload = _snapshot(capture, tz="Not/AZone")
        ts = _resting_rows(payload)[0]["timestamp"].astimezone(ZoneInfo("UTC"))
        self.assertEqual(2, ts.hour)

    def test_no_resting_value_emits_no_row(self) -> None:
        payload = _snapshot(datetime(2026, 6, 20, 14, 0, tzinfo=IST))
        del payload["restingHrBpm"]
        self.assertEqual([], _resting_rows(payload))

    def test_steps_still_use_sync_timestamp(self) -> None:
        # Steps must NOT be anchored — multiple readings/day is correct.
        capture = datetime(2026, 6, 20, 14, 0, tzinfo=IST)
        payload = _snapshot(capture)
        payload["stepsToday"] = 8000
        rows = extract_observations(payload, source="health_connect")
        steps = [r for r in rows if r["metric_type"] == "steps_today"][0]
        self.assertEqual(_ms(capture), int(steps["timestamp"].timestamp() * 1000))


if __name__ == "__main__":
    unittest.main()
