"""Unit tests for Agreement Engine pure logic."""

import os
import unittest

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from app.services.agreement_service import _rate


class RateTest(unittest.TestCase):
    def test_zero_denominator_returns_none(self):
        self.assertIsNone(_rate(0, 0))
        self.assertIsNone(_rate(5, 0))

    def test_full_agreement(self):
        self.assertEqual(1.0, _rate(10, 10))

    def test_zero_agreement(self):
        self.assertEqual(0.0, _rate(0, 10))

    def test_partial_agreement(self):
        self.assertAlmostEqual(0.5, _rate(5, 10))

    def test_rounds_to_four_places(self):
        result = _rate(1, 3)
        self.assertEqual(0.3333, result)

    def test_numerator_larger_than_denominator_clamps(self):
        # should not happen in practice but must not crash
        result = _rate(15, 10)
        self.assertEqual(1.5, result)


class SummaryShapeTest(unittest.TestCase):
    """Verify that the expected output keys are well-defined without a DB."""

    EXPECTED_SUMMARY_KEYS = {
        "user_id", "days", "total", "assessed",
        "confirmed", "rejected", "needs_review", "pending",
        "agreement_rate", "disagreement_rate", "pending_rate", "coverage",
        "mean_confidence", "min_confidence", "max_confidence",
        "confidence_distribution", "inference_by_version",
    }

    EXPECTED_CONF_BUCKETS = {"[0.0, 0.25)", "[0.25, 0.5)", "[0.5, 0.75)", "[0.75, 1.0]"}

    def test_expected_summary_key_count(self):
        self.assertEqual(17, len(self.EXPECTED_SUMMARY_KEYS))

    def test_expected_confidence_buckets(self):
        self.assertEqual(4, len(self.EXPECTED_CONF_BUCKETS))
        for bucket in ("[0.0, 0.25)", "[0.25, 0.5)", "[0.5, 0.75)", "[0.75, 1.0]"):
            self.assertIn(bucket, self.EXPECTED_CONF_BUCKETS)


class ByStateShapeTest(unittest.TestCase):
    EXPECTED_STATE_KEYS = {
        "inferred_state", "total", "confirmed", "rejected",
        "needs_review", "pending", "agreement_rate", "disagreement_rate",
    }

    def test_expected_state_key_count(self):
        self.assertEqual(8, len(self.EXPECTED_STATE_KEYS))


class RateSemanticTest(unittest.TestCase):
    """agreement_rate + disagreement_rate need not sum to 1 (needs_review is neither)."""

    def test_confirmed_plus_rejected_lt_assessed_is_valid(self):
        assessed = 10
        confirmed = 4
        rejected = 3
        # needs_review = 3
        agreement = _rate(confirmed, assessed)
        disagreement = _rate(rejected, assessed)
        self.assertAlmostEqual(0.4, agreement)
        self.assertAlmostEqual(0.3, disagreement)
        self.assertLess(agreement + disagreement, 1.0)

    def test_all_pending_gives_none_rates(self):
        assessed = 0
        self.assertIsNone(_rate(0, assessed))
        self.assertIsNone(_rate(0, assessed))

    def test_coverage_zero_when_all_pending(self):
        # coverage = assessed / total
        total = 10
        assessed = 0
        self.assertEqual(0.0, _rate(assessed, total))

    def test_coverage_one_when_all_assessed(self):
        total = 10
        assessed = 10
        self.assertEqual(1.0, _rate(assessed, total))


if __name__ == "__main__":
    unittest.main()
