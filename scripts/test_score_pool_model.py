import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_pool_model import calibrated_confidence, calibrated_score_pool


class ScorePoolCalibrationTests(unittest.TestCase):
    def test_balanced_market_keeps_nil_nil_and_symmetric_single_goal_paths(self):
        scores = [("1-1", 5.2), ("1-0", 6.0), ("0-1", 6.4), ("0-0", 8.0), ("2-1", 9.0)]
        probs = {"home": 0.37, "draw": 0.30, "away": 0.33}
        main, backups, tails, _ = calibrated_score_pool(scores, probs, [("2", 3.1)])
        pool = [main, *backups]
        self.assertTrue({"0-0", "1-0", "0-1"}.issubset(pool))
        self.assertEqual(tails, [])

    def test_strong_home_keeps_clean_sheet_extension_and_tail(self):
        scores = [("2-0", 6.5), ("1-0", 7.0), ("2-1", 7.2), ("3-0", 12.0), ("1-1", 9.0)]
        probs = {"home": 0.66, "draw": 0.20, "away": 0.14}
        main, backups, tails, _ = calibrated_score_pool(scores, probs, [("3", 3.4)])
        self.assertEqual(main, "2-0")
        self.assertIn("3-0", [main, *backups])
        self.assertIn("3-0", tails)

    def test_strong_away_keeps_zero_two(self):
        scores = [("0-1", 6.0), ("1-2", 6.8), ("0-2", 7.0), ("1-1", 8.0)]
        probs = {"home": 0.18, "draw": 0.20, "away": 0.62}
        main, backups, _, _ = calibrated_score_pool(scores, probs, [("2", 3.0)])
        self.assertIn("0-2", [main, *backups])

    def test_confidence_is_capped(self):
        self.assertLessEqual(calibrated_confidence({"home": 0.90, "draw": 0.06, "away": 0.04}, "home"), 88)


if __name__ == "__main__":
    unittest.main()
