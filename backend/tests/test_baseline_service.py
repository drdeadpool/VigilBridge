"""Unit tests for Baseline Engine v1 pure logic: severity, rounding, assembly."""

import os
import unittest

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from app.services.baseline_service import (
    BASELINE_METRICS,
    METRIC_DAILY_AGG,
    _round,
    _stats_from_row,
    assemble_status,
    severity,
)


class SeverityTest(unittest.TestCase):
    def test_within_one_sd_is_normal(self):
        self.assertEqual(0, severity(10.5, 10.0, 1.0))   # z=0.5

    def test_at_one_sd_is_mild(self):
        self.assertEqual(1, severity(11.0, 10.0, 1.0))   # z=1.0 -> Mild

    def test_mild_band(self):
        self.assertEqual(1, severity(11.5, 10.0, 1.0))   # z=1.5

    def test_at_two_sd_is_moderate(self):
        self.assertEqual(2, severity(12.0, 10.0, 1.0))   # z=2.0

    def test_at_three_sd_is_severe(self):
        self.assertEqual(3, severity(13.0, 10.0, 1.0))   # z=3.0

    def test_beyond_three_sd_is_severe(self):
        self.assertEqual(3, severity(99.0, 10.0, 1.0))

    def test_zero_std_is_normal(self):
        self.assertEqual(0, severity(10.0, 10.0, 0.0))

    def test_missing_today_is_normal(self):
        self.assertEqual(0, severity(None, 10.0, 1.0))

    def test_below_mean_uses_absolute_distance(self):
        self.assertEqual(2, severity(7.5, 10.0, 1.0))    # z=2.5


class RoundTest(unittest.TestCase):
    def test_steps_rounds_to_int(self):
        self.assertEqual(8421, _round("steps_today", 8421.33))
        self.assertIsInstance(_round("steps_today", 8421.33), int)

    def test_sleep_rounds_two_decimals(self):
        self.assertEqual(7.05, _round("sleep_duration_hours", 7.0512))

    def test_none_passes_through(self):
        self.assertIsNone(_round("steps_today", None))


class StatsFromRowTest(unittest.TestCase):
    def test_skips_null_metrics(self):
        row = {
            "sleep_mean": 7.0, "sleep_std": 0.6,
            "rhr_mean": None, "rhr_std": None,
            "steps_mean": 8000.0, "steps_std": 2000.0,
        }
        stats = _stats_from_row(row)
        self.assertIn("sleep_duration_hours", stats)
        self.assertIn("steps_today", stats)
        self.assertNotIn("resting_hr_bpm", stats)


class AssembleStatusTest(unittest.TestCase):
    def test_full_payload_shape(self):
        stats = {
            "sleep_duration_hours": (7.05, 0.62),
            "resting_hr_bpm": (56.4, 2.5),
            "steps_today": (8421.3, 2103.7),
        }
        today = {"sleep_duration_hours": 6.20, "resting_hr_bpm": 60.0, "steps_today": 5100.0}
        out = assemble_status("u1", "2026-06-22T18:30:00+00:00", 13, stats, today)

        self.assertEqual("u1", out["user_id"])
        self.assertEqual(13, out["valid_days"])
        self.assertEqual(2026, 2026)
        self.assertEqual(
            {"baseline": 7.05, "today": 6.2, "std": 0.62, "severity": 1},
            out["sleep_duration_hours"],
        )
        self.assertEqual(8421, out["steps_today"]["baseline"])
        self.assertEqual(5100, out["steps_today"]["today"])
        # steps z=(8421.3-5100)/2103.7=1.58 -> Mild
        self.assertEqual(1, out["steps_today"]["severity"])
        # rhr z=(60-56.4)/2.5=1.44 -> Mild
        self.assertEqual(1, out["resting_hr_bpm"]["severity"])

    def test_missing_metric_is_null(self):
        stats = {"sleep_duration_hours": (7.0, 0.5)}
        out = assemble_status("u1", "t", 5, stats, {"sleep_duration_hours": 7.0})
        self.assertIsNone(out["resting_hr_bpm"])
        self.assertIsNone(out["steps_today"])


class ScopeTest(unittest.TestCase):
    def test_exactly_three_metrics_in_scope(self):
        self.assertEqual(
            {"sleep_duration_hours", "steps_today", "resting_hr_bpm"},
            set(BASELINE_METRICS),
        )

    def test_steps_reduction_is_max(self):
        self.assertEqual("max", METRIC_DAILY_AGG["steps_today"])

    def test_sleep_and_hr_reduction_is_avg(self):
        self.assertEqual("avg", METRIC_DAILY_AGG["sleep_duration_hours"])
        self.assertEqual("avg", METRIC_DAILY_AGG["resting_hr_bpm"])


if __name__ == "__main__":
    unittest.main()
