import unittest

from generate_date_pages import competition_score_pool, shrink_review_profile


class ReviewShrinkageTests(unittest.TestCase):
    def test_small_sample_adjustments_are_tempered(self):
        profile = {
            "review_sample": 4,
            "had": .32,
            "crs": .50,
            "prior": .18,
            "goal_shift": -.24,
            "draw_boost": 1.20,
            "clean_sheet_boost": 1.16,
            "confidence_delta": -4,
        }
        effective = shrink_review_profile(profile)
        self.assertAlmostEqual(effective["review_strength"], .25)
        self.assertAlmostEqual(effective["goal_shift"], -.06)
        self.assertAlmostEqual(effective["draw_boost"], 1.05)
        self.assertAlmostEqual(effective["clean_sheet_boost"], 1.04)
        self.assertEqual(effective["confidence_delta"], -1)
        self.assertAlmostEqual(effective["had"] + effective["crs"] + effective["prior"], 1.0)


class DiverseScorePoolTests(unittest.TestCase):
    def setUp(self):
        self.match = {"odds": {"crs": {
            "0-0": "8.00", "1-0": "7.00", "2-0": "8.50", "2-1": "6.00",
            "1-1": "6.50", "1-2": "9.00", "0-1": "10.00", "0-2": "14.00",
        }}}
        self.profile = {"clean_sheet_boost": 1.0}

    def test_uncertain_direction_gets_clean_sheet_and_draw_shapes(self):
        main, backups, _ = competition_score_pool(
            self.match,
            {"home": .40, "draw": .32, "away": .28},
            {"0": .08, "1": .12, "2": .40, "3": .30, "4": .10},
            self.profile,
            {},
        )
        self.assertEqual(main, "2-1")
        self.assertTrue(any("0" in score.split("-") for score in backups))
        self.assertTrue(any(score.split("-")[0] == score.split("-")[1] for score in backups))
        self.assertEqual(len({main, *backups}), 3)

    def test_zero_zero_is_promoted_only_under_conditional_low_goal_risk(self):
        _, backups, tails = competition_score_pool(
            self.match,
            {"home": .42, "draw": .30, "away": .28},
            {"0": .08, "1": .12, "2": .40, "3": .30, "4": .10},
            self.profile,
            {},
        )
        self.assertIn("0-0", backups)
        self.assertNotIn("0-0", tails)


if __name__ == "__main__":
    unittest.main()
