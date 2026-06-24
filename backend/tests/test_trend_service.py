"""Unit tests for Trend Engine v1 pure logic: slope, direction, scope reuse."""

import os
import unittest
from datetime import date, timedelta

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from app.services.baseline_service import METRIC_DAILY_AGG
from app.services.trend_service import (
    METRIC_DIRECTION_OF_GOOD,
    TREND_METRICS,
    compute_trend,
)


def _series(values, start="2026-06-01"):
    d0 = date.fromisoformat(start)
    return [
        {"date": (d0 + timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(values)
    ]


class ComputeTrendTest(unittest.TestCase):
    def test_increasing_sleep_is_improving(self):
        t = compute_trend(_series([6.0, 6.5, 7.0, 7.5]), "sleep_duration_hours")
        self.assertEqual("improving", t["direction"])
        self.assertGreater(t["slope_per_day"], 0)
        self.assertEqual(4, t["n_days"])
        self.assertEqual(1.5, t["delta"])
        self.assertEqual(6.0, t["first"])
        self.assertEqual(7.5, t["last"])

    def test_decreasing_sleep_is_deteriorating(self):
        t = compute_trend(_series([8.0, 7.0, 6.0]), "sleep_duration_hours")
        self.assertEqual("deteriorating", t["direction"])
        self.assertLess(t["slope_per_day"], 0)

    def test_increasing_steps_is_improving(self):
        t = compute_trend(_series([3000, 5000, 8000]), "steps_today")
        self.assertEqual("improving", t["direction"])

    def test_rising_resting_hr_is_deteriorating(self):
        # resting_hr: lower is better, so a rising slope = deteriorating
        t = compute_trend(_series([55, 57, 60]), "resting_hr_bpm")
        self.assertEqual("deteriorating", t["direction"])
        self.assertGreater(t["slope_per_day"], 0)

    def test_falling_resting_hr_is_improving(self):
        t = compute_trend(_series([62, 59, 55]), "resting_hr_bpm")
        self.assertEqual("improving", t["direction"])
        self.assertLess(t["slope_per_day"], 0)

    def test_all_equal_is_stable(self):
        t = compute_trend(_series([7.0, 7.0, 7.0, 7.0]), "sleep_duration_hours")
        self.assertEqual("stable", t["direction"])
        self.assertEqual(0.0, t["slope_per_day"])
        self.assertEqual(0.0, t["delta"])

    def test_single_point_is_stable(self):
        t = compute_trend(_series([7.0]), "sleep_duration_hours")
        self.assertEqual("stable", t["direction"])
        self.assertEqual(1, t["n_days"])
        self.assertEqual(0.0, t["slope_per_day"])
        self.assertEqual(7.0, t["first"])
        self.assertEqual(7.0, t["last"])

    def test_empty_series_is_stable(self):
        t = compute_trend([], "steps_today")
        self.assertEqual("stable", t["direction"])
        self.assertEqual(0, t["n_days"])
        self.assertIsNone(t["first"])

    def test_slope_handles_day_gaps(self):
        # Two points 10 days apart, +10.0 total -> slope 1.0/day regardless of gap.
        series = [
            {"date": "2026-06-01", "value": 50.0},
            {"date": "2026-06-11", "value": 60.0},
        ]
        t = compute_trend(series, "steps_today")
        self.assertEqual(1.0, t["slope_per_day"])


class ScopeTest(unittest.TestCase):
    def test_trend_metrics_are_baseline_three(self):
        self.assertEqual(
            {"sleep_duration_hours", "steps_today", "resting_hr_bpm"},
            set(TREND_METRICS),
        )

    def test_reuses_baseline_daily_agg(self):
        # aggregation selection: trend reuses the Baseline reduction map, not its own
        self.assertEqual("max", METRIC_DAILY_AGG["steps_today"])
        self.assertEqual("avg", METRIC_DAILY_AGG["sleep_duration_hours"])
        self.assertEqual("avg", METRIC_DAILY_AGG["resting_hr_bpm"])

    def test_direction_of_good_inverts_resting_hr(self):
        self.assertEqual(-1, METRIC_DIRECTION_OF_GOOD["resting_hr_bpm"])
        self.assertEqual(1, METRIC_DIRECTION_OF_GOOD["sleep_duration_hours"])
        self.assertEqual(1, METRIC_DIRECTION_OF_GOOD["steps_today"])


if __name__ == "__main__":
    unittest.main()
