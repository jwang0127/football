import unittest

from three_layer_model import calculate_three_layer


def evidence(home=70, away=50):
    return {
        "enabled": True,
        "drawCaution": 0.04,
        "hardStrength": {"home": {k: home for k in ("leagueRanking", "squadValue", "recentForm", "venueAttribute")}, "away": {k: away for k in ("leagueRanking", "squadValue", "recentForm", "venueAttribute")}},
        "tacticalMatchup": {"home": {k: home for k in ("styleMatchup", "headToHead", "coreAvailability")}, "away": {k: away for k in ("styleMatchup", "headToHead", "coreAvailability")}},
        "psychologicalState": {"home": {k: home for k in ("lastResult", "scheduleFitness", "motivation")}, "away": {k: away for k in ("lastResult", "scheduleFitness", "motivation")}},
    }


class ThreeLayerModelTests(unittest.TestCase):
    def test_weighted_layers_produce_home_edge(self):
        result = calculate_three_layer({"threeLayer": evidence()})
        self.assertTrue(result["enabled"])
        self.assertGreater(result["totalScores"]["home"], result["totalScores"]["away"])
        self.assertGreater(result["probabilities"]["home"], result["probabilities"]["away"])
        self.assertEqual(result["dataCompleteness"], 1.0)

    def test_missing_items_are_neutral_and_reduce_confidence(self):
        result = calculate_three_layer({"threeLayer": {"enabled": True}})
        self.assertEqual(result["totalScores"], {"home": 50.0, "away": 50.0})
        self.assertEqual(result["dataCompleteness"], 0.0)
        self.assertLess(result["confidencePenalty"], 0)
        self.assertEqual(len(result["missingItems"]), 20)

    def test_disabled_context_does_not_change_existing_pipeline(self):
        result = calculate_three_layer({})
        self.assertFalse(result["enabled"])


if __name__ == "__main__":
    unittest.main()
