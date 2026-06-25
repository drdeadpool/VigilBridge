"""Unit tests for Human State Estimator v0.1 pure inference."""

import os
import unittest

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from app.services.constraint_engine import evaluate_constraints
from app.services.state_service import STATES, build_evidence_refs, infer_state


def _today_full(sleep=7.0, steps=8000.0, rhr=57.0) -> dict:
    return {"sleep_duration_hours": sleep, "steps_today": steps, "resting_hr_bpm": rhr}


def _stats_typical() -> dict:
    return {
        "sleep_duration_hours": (7.0, 0.5),
        "steps_today": (8500.0, 1500.0),
        "resting_hr_bpm": (56.0, 2.0),
    }


class StateSpaceTest(unittest.TestCase):
    def test_state_vocabulary_frozen(self):
        self.assertEqual(
            ("data_gap", "recovery_deficit", "strain_overshoot", "active_recovery", "normal"),
            STATES,
        )


class InsufficientEvidenceTest(unittest.TestCase):
    def test_low_valid_days_yields_data_gap(self):
        constraints = evaluate_constraints(_today_full(), {}, valid_days=1)
        out = infer_state(constraints, _today_full(), valid_days=1)
        self.assertEqual("data_gap", out["state"])
        self.assertEqual(1.0, out["confidence"])

    def test_missing_metric_yields_data_gap(self):
        today = _today_full()
        today["resting_hr_bpm"] = None
        constraints = evaluate_constraints(today, _stats_typical(), valid_days=14)
        out = infer_state(constraints, today, valid_days=14)
        self.assertEqual("data_gap", out["state"])
        self.assertIn("resting_hr_bpm", out["missing_metrics"])


class RecoveryDeficitTest(unittest.TestCase):
    def test_short_sleep_plus_elevated_rhr(self):
        today = _today_full(sleep=5.5, rhr=62.0)
        constraints = evaluate_constraints(today, _stats_typical(), valid_days=14)
        out = infer_state(constraints, today, valid_days=14)
        self.assertEqual("recovery_deficit", out["state"])
        self.assertEqual(["sleep_short", "rhr_elevated"], out["contributing_constraints"])
        self.assertGreater(out["confidence"], 0.0)


class StrainOvershootTest(unittest.TestCase):
    def test_high_steps_plus_elevated_rhr_no_compensating_sleep(self):
        today = _today_full(steps=12000.0, rhr=62.0, sleep=7.0)
        constraints = evaluate_constraints(today, _stats_typical(), valid_days=14)
        out = infer_state(constraints, today, valid_days=14)
        self.assertEqual("strain_overshoot", out["state"])
        self.assertEqual(["steps_high", "rhr_elevated"], out["contributing_constraints"])

    def test_compensating_long_sleep_blocks_strain(self):
        today = _today_full(steps=12000.0, rhr=62.0, sleep=9.0)
        constraints = evaluate_constraints(today, _stats_typical(), valid_days=14)
        out = infer_state(constraints, today, valid_days=14)
        self.assertNotEqual("strain_overshoot", out["state"])


class ActiveRecoveryTest(unittest.TestCase):
    def test_low_steps_plus_long_sleep(self):
        today = _today_full(steps=5000.0, sleep=9.0, rhr=55.0)
        constraints = evaluate_constraints(today, _stats_typical(), valid_days=14)
        out = infer_state(constraints, today, valid_days=14)
        self.assertEqual("active_recovery", out["state"])
        self.assertEqual(["steps_low", "sleep_long"], out["contributing_constraints"])


class NormalTest(unittest.TestCase):
    def test_within_band_yields_normal(self):
        today = _today_full(sleep=7.1, steps=8400.0, rhr=56.5)
        constraints = evaluate_constraints(today, _stats_typical(), valid_days=14)
        out = infer_state(constraints, today, valid_days=14)
        self.assertEqual("normal", out["state"])
        self.assertEqual([], out["contributing_constraints"])
        self.assertEqual(1.0, out["confidence"])


class PriorityTest(unittest.TestCase):
    def test_recovery_outranks_strain_when_both_present(self):
        # sleep_short + rhr_elevated + steps_high all fire; recovery_deficit wins
        today = _today_full(sleep=5.5, steps=12000.0, rhr=62.0)
        constraints = evaluate_constraints(today, _stats_typical(), valid_days=14)
        out = infer_state(constraints, today, valid_days=14)
        self.assertEqual("recovery_deficit", out["state"])


class EvidenceRefsTest(unittest.TestCase):
    def test_evidence_refs_includes_all_metrics(self):
        refs = build_evidence_refs(_today_full(), _stats_typical(), valid_days=14, period_days=30)
        metrics = {b["metric"] for b in refs["baselines_used"]}
        self.assertEqual({"sleep_duration_hours", "steps_today", "resting_hr_bpm"}, metrics)
        self.assertEqual(14, refs["valid_days"])
        self.assertTrue(all(b["period_days"] == 30 for b in refs["baselines_used"]))


if __name__ == "__main__":
    unittest.main()
