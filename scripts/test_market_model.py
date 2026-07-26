import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from market_model import (
    ScorelineModel,
    expected_value,
    fit_scoreline_model,
    implied_probabilities,
)


class ImpliedProbabilityTests(unittest.TestCase):
    def test_probabilities_sum_to_one_and_keep_order(self):
        probs = implied_probabilities({"home": "1.60", "draw": "3.80", "away": "5.20"})
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=9)
        self.assertGreater(probs["home"], probs["draw"])
        self.assertGreater(probs["draw"], probs["away"])

    def test_power_devig_shrinks_longshots_versus_proportional(self):
        odds = {"home": "1.30", "draw": "5.50", "away": "9.00"}
        power = implied_probabilities(odds, method="power")
        proportional = implied_probabilities(odds, method="proportional")
        self.assertLess(power["away"], proportional["away"])
        self.assertGreater(power["home"], proportional["home"])

    def test_invalid_and_missing_prices_are_ignored(self):
        probs = implied_probabilities({"home": "1.85", "draw": "", "away": None, "updatedAt": "x"})
        self.assertEqual(list(probs), ["home"])
        self.assertAlmostEqual(probs["home"], 1.0)
        self.assertEqual(implied_probabilities({}), {})

    def test_expected_value(self):
        self.assertAlmostEqual(expected_value(0.5, 2.2), 0.1)
        self.assertIsNone(expected_value(0.5, None))
        self.assertIsNone(expected_value(None, 2.0))


class ScorelineModelTests(unittest.TestCase):
    def test_fit_recovers_synthetic_poisson_rates(self):
        truth = ScorelineModel(1.6, 0.9, 0.05)
        market = {f"{h}-{a}": p for (h, a), p in truth.matrix.items() if h <= 5 and a <= 5}
        fitted = fit_scoreline_model(market)
        self.assertIsNotNone(fitted)
        self.assertAlmostEqual(fitted.lambda_home, 1.6, delta=0.08)
        self.assertAlmostEqual(fitted.lambda_away, 0.9, delta=0.08)

    def test_other_buckets_anchor_tail_mass(self):
        truth = ScorelineModel(2.4, 0.7, 0.0)
        market: dict[str, float] = {}
        buckets = {"homeOther": 0.0, "drawOther": 0.0, "awayOther": 0.0}
        for (h, a), p in truth.matrix.items():
            if h <= 3 and a <= 3:
                market[f"{h}-{a}"] = p
            else:
                key = "homeOther" if h > a else "awayOther" if h < a else "drawOther"
                buckets[key] += p
        with_buckets = fit_scoreline_model({**market, **buckets})
        without = fit_scoreline_model(market)
        # The truncated matrix alone under-estimates the strong side's rate.
        self.assertLess(abs(with_buckets.lambda_home - 2.4), abs(without.lambda_home - 2.4) + 0.02)

    def test_derived_distributions_are_normalised(self):
        model = ScorelineModel(1.4, 1.1, 0.03)
        for probs in (model.outcome_probabilities(), model.total_goal_probabilities(),
                      model.half_full_probabilities()):
            self.assertAlmostEqual(sum(probs.values()), 1.0, places=6)

    def test_half_full_favours_full_time_direction(self):
        model = ScorelineModel(2.0, 0.7, 0.0)
        hafu = model.half_full_probabilities()
        self.assertGreater(hafu["hh"], hafu["aa"])
        self.assertGreater(hafu["hh"] + hafu["dh"], 0.4)

    def test_score_probabilities_renormalise_over_offered_scores(self):
        model = ScorelineModel(1.2, 1.0, 0.0)
        subset = model.score_probabilities(["1-0", "1-1", "0-1"])
        self.assertAlmostEqual(sum(subset.values()), 1.0, places=9)
        self.assertGreater(subset["1-0"], subset["0-1"])

    def test_degenerate_market_returns_none(self):
        self.assertIsNone(fit_scoreline_model({"1-0": 0.6, "0-1": 0.4}))
        self.assertIsNone(fit_scoreline_model({}))

    def test_fit_divergence_is_small_for_model_generated_market(self):
        truth = ScorelineModel(1.3, 1.0, 0.04)
        market = {f"{h}-{a}": p for (h, a), p in truth.matrix.items() if h <= 5 and a <= 5}
        fitted = fit_scoreline_model(market)
        self.assertLess(fitted.kl_divergence, 0.01)

    def test_grid_handles_extreme_rates_without_math_errors(self):
        model = ScorelineModel(5.5, 0.2, 0.0)
        self.assertTrue(math.isfinite(sum(model.matrix.values())))
        self.assertAlmostEqual(sum(model.matrix.values()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
