"""Unit tests for Constraint Engine v0.1 pure logic."""

import os
import unittest

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from app.services.constraint_engine import (
    FULL_CONFIDENCE_DAYS,
    RULES,
    confidence_from_valid_days,
    evaluate_constraints,
    evaluate_rule,
)


class ConfidenceTest(unittest.TestCase):
    def test_zero_days_is_zero(self):
        self.assertEqual(0.0, confidence_from_valid_days(0))

    def test_half_window_is_half(self):
        self.assertAlmostEqual(0.5, confidence_from_valid_days(FULL_CONFIDENCE_DAYS // 2))

    def test_full_window_is_one(self):
        self.assertEqual(1.0, confidence_from_valid_days(FULL_CONFIDENCE_DAYS))

    def test_overshoot_clamps_to_one(self):
        self.assertEqual(1.0, confidence_from_valid_days(FULL_CONFIDENCE_DAYS * 3))


class RuleEvaluatorTest(unittest.TestCase):
    def test_low_side_fires_below_one_sd(self):
        out = evaluate_rule("sleep_short", "sleep_duration_hours", -1, 5.0, 7.0, 1.0, 14)
        self.assertTrue(out["fires"])
        self.assertEqual(2, out["severity"])
        self.assertEqual(-2.0, out["evidence"]["z"])

    def test_low_side_does_not_fire_above_mean(self):
        out = evaluate_rule("sleep_short", "sleep_duration_hours", -1, 8.0, 7.0, 1.0, 14)
        self.assertFalse(out["fires"])
        self.assertEqual(0, out["severity"])

    def test_high_side_fires_above_one_sd(self):
        out = evaluate_rule("rhr_elevated", "resting_hr_bpm", +1, 60.0, 56.0, 2.0, 14)
        self.assertTrue(out["fires"])
        self.assertEqual(2, out["severity"])

    def test_high_side_does_not_fire_below_mean(self):
        out = evaluate_rule("rhr_elevated", "resting_hr_bpm", +1, 50.0, 56.0, 2.0, 14)
        self.assertFalse(out["fires"])

    def test_within_one_sd_does_not_fire(self):
        out = evaluate_rule("sleep_short", "sleep_duration_hours", -1, 6.5, 7.0, 1.0, 14)
        self.assertFalse(out["fires"])

    def test_missing_today_does_not_fire(self):
        out = evaluate_rule("sleep_short", "sleep_duration_hours", -1, None, 7.0, 1.0, 14)
        self.assertFalse(out["fires"])
        self.assertIsNone(out["evidence"]["z"])

    def test_zero_std_does_not_fire(self):
        out = evaluate_rule("sleep_short", "sleep_duration_hours", -1, 5.0, 7.0, 0.0, 14)
        self.assertFalse(out["fires"])

    def test_evidence_payload_shape(self):
        out = evaluate_rule("steps_low", "steps_today", -1, 1000.0, 8000.0, 1500.0, 14)
        ev = out["evidence"]
        for key in ("metric", "direction", "today", "baseline_mean", "baseline_std", "z", "valid_days"):
            self.assertIn(key, ev)
        self.assertEqual("steps_today", ev["metric"])
        self.assertEqual(-1, ev["direction"])

    def test_confidence_scales_with_valid_days(self):
        a = evaluate_rule("sleep_short", "sleep_duration_hours", -1, 5.0, 7.0, 1.0, 3)
        b = evaluate_rule("sleep_short", "sleep_duration_hours", -1, 5.0, 7.0, 1.0, 14)
        self.assertLess(a["confidence"], b["confidence"])


class EvaluateAllConstraintsTest(unittest.TestCase):
    def test_six_rules_emitted(self):
        out = evaluate_constraints(
            today_values={
                "sleep_duration_hours": 6.5,
                "steps_today": 8000.0,
                "resting_hr_bpm": 57.0,
            },
            stats={
                "sleep_duration_hours": (7.0, 0.5),
                "steps_today": (8500.0, 1500.0),
                "resting_hr_bpm": (56.0, 2.0),
            },
            valid_days=14,
        )
        self.assertEqual(6, len(out))
        self.assertEqual({r[0] for r in RULES}, {c["name"] for c in out})

    def test_recovery_signature_fires(self):
        out = evaluate_constraints(
            today_values={
                "sleep_duration_hours": 5.5,
                "steps_today": 7000.0,
                "resting_hr_bpm": 62.0,
            },
            stats={
                "sleep_duration_hours": (7.0, 0.5),
                "steps_today": (8500.0, 1500.0),
                "resting_hr_bpm": (56.0, 2.0),
            },
            valid_days=14,
        )
        fired = {c["name"] for c in out if c["fires"]}
        self.assertIn("sleep_short", fired)
        self.assertIn("rhr_elevated", fired)

    def test_no_baseline_produces_no_fires(self):
        out = evaluate_constraints(
            today_values={"sleep_duration_hours": 5.0, "steps_today": 1000.0, "resting_hr_bpm": 70.0},
            stats={},
            valid_days=1,
        )
        self.assertEqual(0, sum(1 for c in out if c["fires"]))


if __name__ == "__main__":
    unittest.main()
