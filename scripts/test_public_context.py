import unittest

from build_public_context import fundamental_layer, head_to_head, team_stats


class PublicContextTests(unittest.TestCase):
    def test_head_to_head_uses_current_home_team_perspective(self):
        match = {"homeCode": "A", "awayCode": "B"}
        history = [
            {"matchId": "1", "matchDate": "20260801", "homeCode": "A", "awayCode": "B", "result": {"homeGoals": 2, "awayGoals": 0}, "league": "测试联赛"},
            {"matchId": "2", "matchDate": "20260701", "homeCode": "B", "awayCode": "A", "result": {"homeGoals": 1, "awayGoals": 1}, "league": "测试联赛"},
        ]
        h2h = head_to_head(match, history)
        self.assertEqual(h2h["sample"], 2)
        self.assertEqual((h2h["wins"], h2h["draws"], h2h["losses"]), (1, 1, 0))
        self.assertTrue(h2h["unbeaten"])
        self.assertIn("未负", h2h["summary"])

    def test_team_stats_tracks_scoring_and_clean_sheets(self):
        history = [
            {"date": "20260801", "team": "A", "opponent": "B", "venue": "home", "gf": 3, "ga": 0, "result": "W"},
            {"date": "20260804", "team": "A", "opponent": "C", "venue": "away", "gf": 1, "ga": 2, "result": "L"},
            {"date": "20260807", "team": "A", "opponent": "D", "venue": "home", "gf": 0, "ga": 0, "result": "D"},
        ]
        stats = team_stats(history)
        self.assertEqual(stats["sample"], 3)
        self.assertAlmostEqual(stats["gf"], 1.333, places=3)
        self.assertAlmostEqual(stats["cleanSheetRate"], 2 / 3, places=3)
        self.assertAlmostEqual(stats["over25Rate"], 2 / 3, places=3)

    def test_fundamental_layer_exposes_upset_and_goal_inputs(self):
        context = fundamental_layer(
            {"homeRank": 5, "awayRank": 15},
            [{"date": "20260810", "venue": "home", "gf": 2, "ga": 1, "result": "W"}],
            [{"date": "20260810", "venue": "away", "gf": 1, "ga": 2, "result": "L"}],
            "20260815",
            "欧洲冠军联赛",
        )
        self.assertIn("fundamentalProbabilities", context)
        self.assertIn("upsetTriggers", context)
        self.assertIn("cupModelInputs", context)
        self.assertIn("home", context["fundamentalStats"])


if __name__ == "__main__":
    unittest.main()
