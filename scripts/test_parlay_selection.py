import unittest

from generate_date_pages import score_leg_eligible, score_shapes_are_distinct


class ParlaySelectionTests(unittest.TestCase):
    def test_exact_score_requires_match_evidence_and_confidence(self):
        blocked = {"market": "crs", "evidenceGate": "blocked", "confidenceScore": 80}
        weak = {"market": "crs", "evidenceGate": "passed", "confidenceScore": 54}
        passed = {"market": "crs", "evidenceGate": "passed", "confidenceScore": 55}
        self.assertFalse(score_leg_eligible(blocked))
        self.assertFalse(score_leg_eligible(weak))
        self.assertTrue(score_leg_eligible(passed))

    def test_score_shapes_must_not_repeat(self):
        self.assertFalse(score_shapes_are_distinct([
            {"market": "crs", "pick": "1-2"},
            {"market": "crs", "pick": "2-1"},
        ]))
        self.assertTrue(score_shapes_are_distinct([
            {"market": "crs", "pick": "1-2"},
            {"market": "crs", "pick": "0-0"},
        ]))


if __name__ == "__main__":
    unittest.main()
