import unittest

from generate_date_pages import (
    build_dimension_report,
    competition_score_pool,
    context_for_match,
    market_volatility_audit,
    model_profile_for,
    shrink_review_profile,
)


class ReviewShrinkageTests(unittest.TestCase):
    def test_unknown_competition_gets_its_own_neutral_model(self):
        profile = model_profile_for("测试新杯赛")
        self.assertEqual(profile["modelScope"], "dedicated_competition")
        self.assertLessEqual(profile["review_sample"], 1)
        self.assertIn("auto-", profile["version"])
        self.assertIn("测试新杯赛", profile["lesson"])
        self.assertIn("researchPack", profile)
        self.assertIn("missingDimensions", profile["researchPack"])

    def test_cup_model_version_is_not_overwritten_by_auto_calibration(self):
        for league in ("欧洲冠军联赛", "欧罗巴联赛", "巴西杯", "南美解放者杯"):
            profile = model_profile_for(league)
            self.assertIn("cup", profile["version"])
            if league == "南美解放者杯":
                self.assertIn("calibrationVersion", profile)

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

    def test_rest_advantage_is_structured_and_requires_evidence(self):
        base = {"sources": [{"name": "official", "url": "https://example.test"}], "verifiedFactors": ["schedule"], "homeRestDays": 5, "awayRestDays": 2}
        context = context_for_match({}, base)
        self.assertGreater(context["outcomeMultipliers"]["home"], 1.0)
        self.assertLess(context["outcomeMultipliers"]["away"], 1.0)
        self.assertIn("休息天数", context["restFatigue"])
        self.assertEqual(build_dimension_report({}, context)["adjustmentGate"], "passed")


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


class CupModelTests(unittest.TestCase):
    def test_efl_cup_uses_rotation_cap_and_lower_scoreline_weight(self):
        profile = model_profile_for("英格兰联赛杯")
        self.assertEqual(profile["confidence_cap"], 64)
        self.assertAlmostEqual(profile["scoreline_weight"], .18)
        self.assertAlmostEqual(profile["structural_goal_shift"], -.04)

    def test_efl_cup_penalizes_unknown_lineups_and_reports_draw_risk(self):
        audit = market_volatility_audit(
            {"league": "英格兰联赛杯"},
            {"home": .44, "draw": .34, "away": .22},
            {"0": .12, "1": .28, "2": .30, "3": .18, "4": .08, "5": .04, "6": 0.0, "7+": 0.0},
            {"verifiedFactors": []},
            model_profile_for("英格兰联赛杯"),
        )
        self.assertEqual(audit["confidenceCap"], 64)
        self.assertLessEqual(audit["confidencePenalty"], -10)
        self.assertTrue(any("轮换" in factor for factor in audit["factors"]))

    def test_narrow_efl_cup_direction_keeps_draw_score_hedge(self):
        main, backups, _ = competition_score_pool(
            {"league": "英格兰联赛杯", "odds": {"crs": {
                "0-0": "8.00", "1-0": "7.00", "2-0": "8.50", "2-1": "6.00",
                "1-1": "6.50", "1-2": "9.00", "0-1": "10.00", "0-2": "14.00",
            }}},
            {"home": .44, "draw": .34, "away": .22},
            {"0": .08, "1": .12, "2": .40, "3": .30, "4": .10},
            {"clean_sheet_boost": 1.0},
            {},
            scoreline_weight=.18,
        )
        self.assertNotEqual(main, "1-1")
        self.assertIn("1-1", backups)


class NewlySupportedCompetitionTests(unittest.TestCase):
    def test_j2_has_an_isolated_conservative_profile(self):
        profile = model_profile_for("日本乙级联赛")
        self.assertTrue(profile["version"].startswith("j2-league-v1-dedicated-0809"))
        self.assertLessEqual(profile["review_sample"], 1)
        self.assertAlmostEqual(sum(profile["prior_probs"]), 1.0)
        self.assertLessEqual(profile["confidence_delta"], -8)


if __name__ == "__main__":
    unittest.main()
